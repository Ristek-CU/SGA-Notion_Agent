import pytest
from app.webhook.guard import check_out_of_scope


def test_guard_whitelist():
    res = check_out_of_scope("bikin tiket ristek error login")
    assert res["is_out_of_scope"] is False


def test_guard_programming_block():
    res = check_out_of_scope("tulisin kode python untuk scraping web")
    assert res["is_out_of_scope"] is True
    assert "kode" in res["reason"] or "pemograman" in res["reason"]


def test_guard_oos_block():
    res = check_out_of_scope("bagaimana ramalan zodiak leo hari ini")
    assert res["is_out_of_scope"] is True


def test_guard_normal_msg():
    res = check_out_of_scope("halo selamat pagi")
    assert res["is_out_of_scope"] is False
