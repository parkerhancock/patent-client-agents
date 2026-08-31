"""Parser tests using representative official-page markup."""

from patent_client_agents.china_spc_ip_court import (
    parse_hearing_index,
    parse_hearing_notice,
    parse_site_search,
)
from patent_client_agents.china_spc_ip_court.client import _split_case_clause

INDEX_HTML = """
<div class="listing"><ul><li>
  <span class="left"><a href="/zh-cn/news/view-5999.html">最高人民法院知识产权法庭2026年8月21日开庭公告</a></span>
  <span class="right">2026-08-19</span>
</li></ul></div>
<div class="pagination"><a href="/zh-cn/news/more-4-15.html?page=2">下一页</a>
<a href="/zh-cn/news/more-4-15.html?page=388">尾页</a></div>
"""

DETAIL_HTML = """
<div class="detail">
 <h2>最高人民法院知识产权法庭2026年8月21日开庭公告</h2>
 <div class="message"><span>发布时间：2026-08-19 16:05:44</span><span>来源：最高人民法院知识产权法庭</span></div>
 <div class="txt">最高人民法院知识产权法庭定于二〇二六年八月二十一日上午九时在最高人民法院知识产权法庭第五法庭公开开庭审理上诉人宁波奥美利合科技有限公司与被上诉人重庆能能科技有限公司及一审被告国家知识产权局发明专利权无效行政纠纷一案。<br/>特此公告。</div>
</div>
"""

SEARCH_HTML = """
<div class="work search_list"><ul class="list"><li>
 <a href="/zh-cn/news/view-5143.html">“锂电池保护芯片”集成电路布图设计侵权案</a>
 <span>集成电路布图设计专有权保护范围的确定</span>
 <i class="date">2025-12-23 04:28:05</i>
</li></ul>
<div class="btm_row pagination"><div class="count">共<span class="num">12</span>篇文章</div>
<a href="/zh-cn/search.html?content=芯片&page=2">2</a></div></div>
"""


def test_parse_hearing_index_and_total_pages() -> None:
    result = parse_hearing_index(INDEX_HTML)
    assert result.total_pages == 388
    assert result.notices[0].notice_id == "5999"
    assert result.notices[0].published_date.isoformat() == "2026-08-19"


def test_parse_hearing_notice_extracts_parties_and_dispute() -> None:
    notice = parse_hearing_notice(
        DETAIL_HTML,
        notice_url="https://ipc.court.gov.cn/zh-cn/news/view-5999.html",
    )
    assert notice.hearing_date.isoformat() == "2026-08-21"
    assert notice.hearing_time_text == "上午九时"
    assert notice.venue == "最高人民法院知识产权法庭第五法庭"
    assert notice.dispute_type == "发明专利权无效行政纠纷"
    assert [party.role_en for party in notice.parties] == [
        "appellant",
        "appellee",
        "first_instance_defendant",
    ]
    assert notice.parties[0].name == "宁波奥美利合科技有限公司"


def test_parse_site_search() -> None:
    result = parse_site_search(SEARCH_HTML, query="芯片")
    assert result.total_count == 12
    assert result.total_pages == 2
    assert result.hits[0].url.endswith("view-5143.html")
    assert result.hits[0].published_at.isoformat() == "2025-12-23T04:28:05"


def test_confirmed_non_infringement_dispute_keeps_complete_cause() -> None:
    parties, dispute = _split_case_clause("原告甲公司与被告乙公司确认不侵害专利权纠纷")
    assert parties == "原告甲公司与被告乙公司"
    assert dispute == "确认不侵害专利权纠纷"
