import subprocess
import sys
import textwrap


def test_production_visual_handler_name_fallback_search_select_and_restart(tmp_path):
    script = textwrap.dedent(
        r'''
        import json
        import sys
        import threading
        import urllib.parse
        import urllib.request
        from http.server import ThreadingHTTPServer
        from pathlib import Path

        from operation_pancake import ocr_team_app_visual, team_app
        from operation_pancake.production.gm import GMProduct
        from operation_pancake.team_import import Candidate, TeamImportState, TeamImportStore

        root = Path.cwd()
        state_path = Path(sys.argv[1])
        roster_path = Path(sys.argv[2])
        store = TeamImportStore(state_path)
        store.save(
            TeamImportState(
                candidates=[
                    Candidate(
                        "rt-fallback",
                        "OFFENSE",
                        "RT1",
                        position="RT",
                        match_status="UNMATCHED",
                    )
                ]
            )
        )

        ocr_team_app_visual.install_runtime()
        handler = team_app.create_handler(
            root,
            team_import_path=state_path,
            roster_path=roster_path,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        try:
            search = urllib.parse.urlencode(
                {"player_name__rt-fallback": "Juan Gaston"}
            ).encode()
            req = urllib.request.Request(
                base + "/team/tackle-search",
                data=search,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                assert response.status == 200

            with urllib.request.urlopen(base + "/api/team-import", timeout=20) as response:
                state = json.load(response)["state"]
            candidate = state["candidates"][0]
            gm = GMProduct(root)

            selected = candidate.get("canonical_card_id")
            if selected:
                assert candidate["player_name"] == "Juan Gaston"
                assert candidate["match_status"] == "MATCHED"
            else:
                fallback = candidate["match_diagnostics"]["user_name_fallback"]
                assert fallback["query"] == "Juan Gaston"
                assert fallback["result_card_ids"]
                offered = [
                    gm.cards[card_id] for card_id in fallback["result_card_ids"]
                ]
                assert all(card.get("position") == "RT" for card in offered)
                assert all(
                    card.get("player_name") == "Juan Gaston" for card in offered
                )
                selected = max(
                    offered,
                    key=lambda card: int(card.get("native_overall") or 0),
                )["card_id"]

                confirm = urllib.parse.urlencode(
                    {"card__rt-fallback": selected}
                ).encode()
                req = urllib.request.Request(
                    base + "/team/confirm",
                    data=confirm,
                    method="POST",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=20) as response:
                    assert response.status == 200

            restarted = TeamImportStore(state_path).load().candidates[0]
            assert restarted.player_name == "Juan Gaston"
            assert restarted.canonical_card_id == selected
            assert restarted.match_status == "MATCHED"
            assert "user-confirmed:cfb27-name-search" in restarted.provenance
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        '''
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path / "team-import.json"),
            str(tmp_path / "roster.json"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
