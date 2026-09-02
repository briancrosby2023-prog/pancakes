from types import SimpleNamespace

from PIL import Image

from operation_pancake import ocr_team_app
from operation_pancake.slot_crop_ocr import ocr_slot_crops
from operation_pancake.team_import import OCRObservation, TeamImportState
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS


def test_exact_slot_crops_record_pixel_coordinates_raw_text_and_tokens(tmp_path, monkeypatch):
    image_path = tmp_path / "special-teams.jpg"
    Image.new("RGB", (2000, 1000), "black").save(image_path)
    region = next(x for x in REAL_TEAM_MANAGER_SLOT_REGIONS["SPECIAL TEAMS"] if x.slot == "KR1")

    def fake_run(executable, image, psm, temp_dir):
        if image.width > image.height * 2 and psm == 7:
            return [("Malachi", 0.91), ("T0NEY", 0.87)], "Malachi T0NEY", ""
        return [], "", ""

    monkeypatch.setattr("operation_pancake.slot_crop_ocr._run", fake_run)
    observations, diagnostics = ocr_slot_crops(image_path, [region], "tesseract")
    name = diagnostics["KR1"]["crops"]["starter_name"]
    assert name["pixel_box"] == [1305, 435, 1450, 476]
    assert name["raw_text"] == "Malachi T0NEY"
    assert name["normalized_tokens"] == ["malachi", "t0ney"]
    assert {word.text for word in observations} == {"Malachi", "T0NEY"}


def test_active_extractor_hands_slot_crop_observations_to_structured_parser(tmp_path, monkeypatch):
    image_path = tmp_path / "special-teams.jpg"
    Image.new("RGB", (2000, 1000), "black").save(image_path)
    state = TeamImportState(
        screenshots=[
            {"id": "shot-1", "filename": "offense.jpg", "path": str(image_path)},
            {"id": "shot-2", "filename": "defense.jpg", "path": str(image_path)},
            {"id": "shot-3", "filename": "special teams.jpg", "path": str(image_path)},
            {"id": "shot-4", "filename": "specialists.jpg", "path": str(image_path)},
        ]
    )

    class Store:
        def load(self):
            return state

        def save(self, value):
            self.value = value

    views = iter(["OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS"])
    monkeypatch.setattr(
        ocr_team_app,
        "_ocr",
        lambda path: [OCRObservation(next(views), (0.01, 0.01, 0.02, 0.02), 0.99)],
    )
    monkeypatch.setattr(
        ocr_team_app,
        "discover_tesseract",
        lambda: SimpleNamespace(ready=True, executable="tesseract"),
    )

    def crops(path, regions, executable):
        if regions[0].slot == "P1":
            return [
                OCRObservation("Malachi", (0.660, 0.435, 0.690, 0.476), 0.91),
                OCRObservation("T0NEY", (0.690, 0.435, 0.720, 0.476), 0.87),
                OCRObservation("89", (0.713, 0.435, 0.740, 0.476), 0.95),
            ], {"KR1": {"crops": {"starter_name": {"raw_text": "Malachi T0NEY"}}}}
        return [], {}

    monkeypatch.setattr(ocr_team_app, "ocr_slot_crops", crops)
    gm = SimpleNamespace(
        population=[
            {
                "card_id": "wr",
                "player_name": "Malachi Toney",
                "position": "WR",
                "native_overall": 89,
                "season": "CFB27",
            }
        ]
    )
    monkeypatch.setattr(
        ocr_team_app,
        "match_candidate",
        __import__(
            "operation_pancake.cfb27_ocr_match", fromlist=["match_candidate_cfb27"]
        ).match_candidate_cfb27,
    )
    result = ocr_team_app._extract_unique(Store(), gm)
    kr = next(x for x in result.candidates if x.slot == "KR1")
    assert kr.canonical_card_id == "wr"
    assert kr.match_diagnostics["candidate_count"] == 1
    assert (
        result.team_observations["screenshots"]["shot-3"]["slot_crop_ocr"]["KR1"]["crops"][
            "starter_name"
        ]["raw_text"]
        == "Malachi T0NEY"
    )
