"""§4 qB state → 统一枚举映射保护。"""
import models as m


def test_downloading():
    assert m.map_qb_state("downloading", 0.3) == m.STATUS_DOWNLOADING
    assert m.map_qb_state("metaDL", 0.0) == m.STATUS_DOWNLOADING


def test_stalled_paused():
    assert m.map_qb_state("stalledDL", 0.1) == m.STATUS_STALLED
    assert m.map_qb_state("pausedDL", 0.1) == m.STATUS_PAUSED


def test_completed_by_upload_states():
    assert m.map_qb_state("uploading", 0.0) == m.STATUS_COMPLETED
    assert m.map_qb_state("pausedUP", 0.0) == m.STATUS_COMPLETED
    assert m.map_qb_state("stalledUP", 0.0) == m.STATUS_COMPLETED


def test_progress_full_forces_completed():
    assert m.map_qb_state("downloading", 1.0) == m.STATUS_COMPLETED


def test_error_wins_even_at_full_progress():
    """error/missingFiles 即便 progress 满也报失败，不能误判 completed。"""
    assert m.map_qb_state("error", 1.0) == m.STATUS_FAILED
    assert m.map_qb_state("missingFiles", 1.0) == m.STATUS_FAILED


def test_unknown_state():
    assert m.map_qb_state("weirdNewState", 0.2) == m.STATUS_UNKNOWN
