from pathlib import Path

from operation_pancake import c3po_roster_app
from operation_pancake.c3po_card_version import C3POCardObservation, C3POCardObservationStore
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterService,
    C3PORosterStore,
    observation_fingerprint,
)


def _multipart(payloads: tuple[bytes, ...]) -> tuple[str, bytes]:
    boundary = "partial-update"
    body = b""
    for index, payload in enumerate(payloads):
        body += (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="screenshots"; '
                f'filename="team-{index}.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
            + payload
            + b"\r\n"
        )
    body += f"--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", body


def test_single_team_manager_screenshot_is_accepted_by_upload_parser(tmp_path: Path):
    content_type, body = _multipart((b"one",))
    paths = c3po_roster_app._uploaded_files(content_type, body, tmp_path)
    assert len(paths) == 1


class _PartialProvider:
    def __init__(self, reads):
        self.reads = reads
        self.request_count = 0

    def read(self, screenshot):
        self.request_count += 1
        return self.reads[screenshot.name]


def _screen(view: str, name: str, slot: str = "X1", ovr: int = 85):
    return {
        "view": view,
        "players": [{"slot": slot, "name": name, "displayed_ovr": ovr}],
        "provider": "fake",
        "model": "fake",
        "status": "C-3PO READ",
    }


def test_single_offense_update_preserves_unsupplied_sections(tmp_path: Path):
    baseline = C3PORoster(
        tuple(
            C3POPlayer(view, "X1", f"Old {view}", 85)
            for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
        ),
        "p",
        "m",
    )
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    service = C3PORosterService(
        store, _PartialProvider({shot.name: _screen("OFFENSE", "New Offense")})
    )

    updated = service.import_screenshots((shot,))

    assert [(p.view, p.name) for p in updated.players] == [
        ("OFFENSE", "New Offense"),
        ("DEFENSE", "Old DEFENSE"),
        ("SPECIAL TEAMS", "Old SPECIAL TEAMS"),
        ("SPECIALISTS", "Old SPECIALISTS"),
    ]


def _baseline() -> C3PORoster:
    return C3PORoster(
        tuple(
            C3POPlayer(view, "X1", f"Old {view}", 85)
            for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS")
        ),
        "p",
        "m",
    )


def test_partial_update_preserves_exact_data_for_unchanged_observations(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    card_store = C3POCardObservationStore(tmp_path / "programs.json")
    defense = baseline.players[1]
    fingerprint = observation_fingerprint(defense, 1)
    card_store.save(
        {
            fingerprint: C3POCardObservation(
                fingerprint,
                defense.name or "",
                85,
                "Phenoms",
                "IDENTIFIED",
                card_id="card-1",
                art_asset="data/production/card_art/card-1.png",
            )
        }
    )
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    service = C3PORosterService(
        store,
        _PartialProvider({shot.name: _screen("OFFENSE", "New Offense")}),
        card_observation_store=card_store,
    )

    updated = service.import_screenshots((shot,))

    updated_defense = next(player for player in updated.players if player.view == "DEFENSE")
    updated_fingerprint = observation_fingerprint(updated_defense, 1)
    preserved = card_store.load()[updated_fingerprint]
    assert preserved.card_id == "card-1"
    assert preserved.art_asset == "data/production/card_art/card-1.png"


def test_partial_update_requires_existing_baseline(tmp_path: Path):
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        _PartialProvider({shot.name: _screen("OFFENSE", "New Offense")}),
    )

    try:
        service.import_screenshots((shot,))
    except ValueError as exc:
        assert "all four" in str(exc).lower()
    else:
        raise AssertionError("partial initial import must fail")


def test_duplicate_partial_sections_fail_without_mutating_roster(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    one = tmp_path / "one.png"
    two = tmp_path / "two.png"
    one.write_bytes(b"1")
    two.write_bytes(b"2")
    provider = _PartialProvider(
        {
            one.name: _screen("OFFENSE", "First"),
            two.name: _screen("OFFENSE", "Second"),
        }
    )
    service = C3PORosterService(store, provider)

    try:
        service.import_screenshots((one, two))
    except ValueError as exc:
        assert "different section" in str(exc).lower()
    else:
        raise AssertionError("duplicate sections must fail")

    assert store.load() == baseline


def test_two_section_update_replaces_only_supplied_sections(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    offense = tmp_path / "offense.png"
    defense = tmp_path / "defense.png"
    offense.write_bytes(b"1")
    defense.write_bytes(b"2")
    provider = _PartialProvider(
        {
            offense.name: _screen("OFFENSE", "New Offense"),
            defense.name: _screen("DEFENSE", "New Defense"),
        }
    )
    service = C3PORosterService(store, provider)

    updated = service.import_screenshots((offense, defense))

    assert [(p.view, p.name) for p in updated.players] == [
        ("OFFENSE", "New Offense"),
        ("DEFENSE", "New Defense"),
        ("SPECIAL TEAMS", "Old SPECIAL TEAMS"),
        ("SPECIALISTS", "Old SPECIALISTS"),
    ]


def test_partial_update_preserves_exact_data_when_occurrence_indexes_shift(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    card_store = C3POCardObservationStore(tmp_path / "programs.json")
    defense = baseline.players[1]
    old_fp = observation_fingerprint(defense, 1)
    card_store.save(
        {
            old_fp: C3POCardObservation(
                old_fp,
                defense.name or "",
                85,
                "Phenoms",
                "IDENTIFIED",
                card_id="card-1",
                art_asset="data/production/card_art/card-1.png",
            )
        }
    )
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    provider = _PartialProvider(
        {
            shot.name: {
                "view": "OFFENSE",
                "players": [
                    {"slot": "X1", "name": "New Offense", "displayed_ovr": 85},
                    {"slot": "Y1", "name": "Extra Offense", "displayed_ovr": 84},
                ],
                "provider": "fake",
                "model": "fake",
                "status": "C-3PO READ",
            }
        }
    )
    service = C3PORosterService(store, provider, card_observation_store=card_store)

    updated = service.import_screenshots((shot,))

    updated_defense = next(player for player in updated.players if player.view == "DEFENSE")
    new_fp = observation_fingerprint(updated_defense, 2)
    preserved = card_store.load()[new_fp]
    assert preserved.card_id == "card-1"
    assert preserved.art_asset == "data/production/card_art/card-1.png"


class _FullProvider:
    def __init__(self):
        self.request_count = 0

    def read_four(self, screenshots):
        self.request_count += 1
        return [
            _screen("OFFENSE", "Full Offense"),
            _screen("DEFENSE", "Full Defense"),
            _screen("SPECIAL TEAMS", "Full Special Teams"),
            _screen("SPECIALISTS", "Full Specialists"),
        ]


def test_four_screenshots_keep_full_refresh_compatibility(tmp_path: Path):
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(_baseline())
    shots = tuple(tmp_path / f"{index}.png" for index in range(4))
    for shot in shots:
        shot.write_bytes(b"x")
    provider = _FullProvider()
    service = C3PORosterService(store, provider)

    updated = service.import_screenshots(shots)

    assert provider.request_count == 1
    assert [player.name for player in updated.players] == [
        "Full Offense",
        "Full Defense",
        "Full Special Teams",
        "Full Specialists",
    ]


def test_unknown_partial_section_fails_without_mutating_roster(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    shot = tmp_path / "unknown.png"
    shot.write_bytes(b"x")
    provider = _PartialProvider({shot.name: _screen("MYSTERY", "Unknown")})
    service = C3PORosterService(store, provider)

    try:
        service.import_screenshots((shot,))
    except ValueError as exc:
        assert "identify every" in str(exc).lower()
    else:
        raise AssertionError("unknown section must fail")

    assert store.load() == baseline


def test_upload_parser_rejects_more_than_four_screenshots(tmp_path: Path):
    content_type, body = _multipart((b"1", b"2", b"3", b"4", b"5"))
    try:
        c3po_roster_app._uploaded_files(content_type, body, tmp_path)
    except ValueError as exc:
        assert "one to four" in str(exc).lower()
    else:
        raise AssertionError("five screenshots must fail")


def test_partial_update_reuses_exact_card_across_name_case_and_display_ovr_change(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    card_store = C3POCardObservationStore(tmp_path / "programs.json")
    offense = baseline.players[0]
    old_fp = observation_fingerprint(offense, 0)
    card_store.save(
        {
            old_fp: C3POCardObservation(
                old_fp,
                offense.name or "",
                85,
                "Phenoms",
                "IDENTIFIED",
                card_id="card-offense",
                art_asset="data/production/card_art/card-offense.png",
            )
        }
    )
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    provider = _PartialProvider({shot.name: _screen("OFFENSE", "OLD OFFENSE", ovr=86)})
    service = C3PORosterService(store, provider, card_observation_store=card_store)

    updated = service.import_screenshots((shot,))

    player = updated.players[0]
    current = card_store.load()[observation_fingerprint(player, 0)]
    assert current.card_id == "card-offense"
    assert current.art_asset == "data/production/card_art/card-offense.png"
    assert current.displayed_ovr == 86


class _EvidenceStore:
    def load_for(self, roster):
        return object()


class _RecordingVersionAnalyzer:
    def __init__(self):
        self.requests = ()

    def analyze_batch(self, requests, evidence):
        self.requests = requests

        class Result:
            request_succeeded = True
            decisions = {}

        return Result()


def test_partial_update_only_analyzes_new_observations(tmp_path: Path):
    baseline = _baseline()
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    card_store = C3POCardObservationStore(tmp_path / "programs.json")
    offense = baseline.players[0]
    old_fp = observation_fingerprint(offense, 0)
    card_store.save(
        {
            old_fp: C3POCardObservation(
                old_fp,
                offense.name or "",
                85,
                "Phenoms",
                "IDENTIFIED",
                card_id="card-old",
                art_asset="data/production/card_art/card-old.png",
            )
        }
    )
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    provider = _PartialProvider(
        {
            shot.name: {
                "view": "OFFENSE",
                "players": [
                    {"slot": "X1", "name": "Old OFFENSE", "displayed_ovr": 86},
                    {"slot": "Y1", "name": "Brand New", "displayed_ovr": 88},
                ],
                "provider": "fake",
                "model": "fake",
                "status": "C-3PO READ",
            }
        }
    )
    analyzer = _RecordingVersionAnalyzer()
    service = C3PORosterService(
        store,
        provider,
        source_evidence_store=_EvidenceStore(),
        version_analyzer=analyzer,
        card_observation_store=card_store,
    )

    service.import_screenshots((shot,))

    assert [request.observation.name for request in analyzer.requests] == ["Brand New"]


def test_partial_update_rejects_section_that_loses_existing_observations(tmp_path: Path):
    baseline = _baseline()
    baseline = C3PORoster(
        (baseline.players[0], C3POPlayer("OFFENSE", "X2", "Backup", 81), *baseline.players[1:]),
        "p",
        "m",
    )
    store = C3PORosterStore(tmp_path / "roster.json")
    store.save(baseline)
    shot = tmp_path / "offense.png"
    shot.write_bytes(b"x")
    service = C3PORosterService(
        store, _PartialProvider({shot.name: _screen("OFFENSE", "New Offense")})
    )

    with pytest.raises(ValueError, match="fewer observations"):
        service.import_screenshots((shot,))

    assert store.load() == baseline


pytest = __import__("pytest")
