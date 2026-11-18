"""
证据回链 / 人工核对测试共用的虚构报告文本与构造函数

全部为虚构数据，只模仿竣工报告的版式，不含任何真实工程内容。
"""
from core.models import DrillHoleEntity, DrillHoleDesignParams, DrillHoleActualParams


# 版式一：按孔号成行的参数表 + 正文段落（模仿真实竣工报告）
ROW_STYLE = """测试矿T巷底板超前钻探竣工报告

工程于2021年3月20日竣工，共施工3个钻孔，现将验收情况汇总如下：

一、任务来源

钻孔施工参数表

| 钻探位置 | 孔号 | 方位 | 倾角 | 开孔位置 | 终孔层位 | 终孔孔深 |
|---|---|---|---|---|---|---|
| 轨道巷12#点前20m正前方向 | T1-1 | 250° | -20° | 3煤 | 8煤底板砂岩 | 80.5m |
| 轨道巷12#点前20m左侧方向 | T1 -2 | 235° | -12° | 3煤 | 6煤顶板砂岩 | 101m |
| 轨道巷12#点前20m | T1-1-J1 | 248° | +6° | 巷道顶板下2.5m | 本溪灰岩 | 60m |

二、钻探情况

1．T1-1钻孔，设计位置：轨道巷12#点前20m；设计方位：250°；设计倾角：-20°；设计孔深：80m。

该孔2021年3月1日早班开孔，实际方位250°，倾角-20°，以φ108mm钻头钻进至20m，孔内下入φ89 mm套管19m。凝固好后用φ75mm钻头扫孔20.5m，使用φ75mm钻头钻进至80.5m位置终孔。

2．T1-2钻孔，设计位置：轨道巷12#点前20m；设计方位：235°；设计倾角：−12°；设计孔深：100m。

该孔2021年3月4日夜班开孔，实际方位235°，倾角-12°，以φ108mm钻头钻进至21m，使用φ75mm钻头钻进至101m位置终孔。

3．T1-1-J1钻孔，设计位置：轨道巷12#点前20m；设计方位：248°；设计倾角：+6°；设计孔深：60m。

该孔2021年3月9日中班开孔，实际方位248°，倾角+6°，以φ94mm钻头钻进至60m位置终孔。

三、结论

以上钻孔施工质量均达到设计要求。
"""


def hole(hid, loc=None, design=None, actual=None):
    return DrillHoleEntity(
        hole_id=hid, location_desc=loc,
        design_params=DrillHoleDesignParams(**(design or {})),
        actual_params=DrillHoleActualParams(**(actual or {})),
    )


def t11(**over):
    """T1-1 的一份完全正确的抽取结果，可用 over 覆盖个别字段"""
    design = dict(design_depth=80, design_azimuth=250, design_inclination=-20)
    actual = dict(actual_depth=80.5, actual_azimuth=250, actual_inclination=-20,
                  start_formation='3煤', end_formation='8煤底板砂岩', drilling_date='2021-03-01')
    loc = over.pop('location_desc', '轨道巷12#点前20m正前方向')
    for k, v in over.items():
        (design if k.startswith('design_') else actual)[k] = v
    return hole('T1-1', loc, design, actual)
