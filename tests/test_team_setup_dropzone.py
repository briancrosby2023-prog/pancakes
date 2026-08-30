from operation_pancake import team_app


def test_dropzone_is_real_multi_file_interaction():
    page = team_app._upload_surface()
    assert 'id="team-dropzone"' in page
    assert 'name="images"' in page and ' multiple ' in page
    for ctype in ("image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"):
        assert ctype in page
    for event in ("dragenter", "dragover", "dragleave", "drop"):
        assert event in page
    assert "e.preventDefault()" in page
    assert "e.stopPropagation()" in page


def test_runtime_marker_and_initialization_state_are_observable_and_truthful():
    page = team_app._upload_surface()
    assert f"TEAM SETUP BUILD: {team_app.TEAM_SETUP_BUILD}" in page
    assert "DROP HANDLER: NOT READY" in page
    assert "DROP HANDLER: INITIALIZING" in page
    assert "DROP HANDLER: ERROR" in page
    assert "setStatus('DROP HANDLER: READY')" in page
    guard = page.index("window.addEventListener(type,pageGuard")
    ready_flag = page.index("zone.dataset.dropReady='1'")
    final_ready = page.rindex("setStatus('DROP HANDLER: READY')")
    assert guard < ready_flag < final_ready


def test_page_level_file_drag_guard_blocks_native_navigation_and_preserves_target_drop():
    page = team_app._upload_surface()
    assert "const isFileDrag=e=>" in page
    assert "['dragenter','dragover','drop'].forEach(type=>window.addEventListener(type,pageGuard,{capture:true,passive:false}))" in page
    assert "if(!zone.contains(e.target)){e.stopPropagation();" in page
    assert "e.dataTransfer.dropEffect='none'" in page
    assert "zone.addEventListener('drop',e=>" in page
    assert "addFiles(e.dataTransfer.files)" in page
    assert "document.addEventListener('DOMContentLoaded',initTeamDrop,{once:true})" in page
    assert "zone.dataset.dropReady='1'" in page
    assert "DROP HANDLER: FILE DRAG" in page


def test_selection_state_and_primary_action_contract():
    page = team_app._upload_surface()
    assert "TEAM SCREENSHOT" in page and "READY" in page
    assert "team-file-list" in page
    assert "b.textContent='REMOVE'" in page
    assert "ADD ANOTHER IMAGE" in page
    assert "ANALYZE MY TEAM" in page
    assert "ANALYZING " in page
    assert "input.click()" in page
    assert "input.files=dt.files" in page
    assert "Array.from(files||[])" in page


def test_invalid_files_are_named_without_discarding_valid_staged_files():
    page = team_app._upload_surface()
    assert "const bad=[]" in page
    assert "bad.push(f.name)" in page
    assert "Unsupported image file" in page
    assert "staged.push(f)" in page


def test_multipart_parser_retains_four_images_together():
    boundary = "PANCAKE-BOUNDARY"
    chunks = []
    expected = []
    for i, ctype in enumerate(("image/png", "image/jpeg", "image/webp", "image/heic"), 1):
        name = f"team-{i}.img"
        data = f"IMAGE-{i}".encode()
        expected.append((name, ctype, data))
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
            + data
            + b"\r\n"
        )
    body = b"".join(chunks) + f"--{boundary}--\r\n".encode()
    parts = team_app._multipart(
        {"Content-Type": f"multipart/form-data; boundary={boundary}"}, body
    )
    files = [(fn, ct, data) for field, fn, ct, data in parts if field == "images"]
    assert files == expected
