/**
 * 农历/黄历本地计算（1900-2100）
 * 说明：宜忌为传统建除十二神参考，不构成任何决策依据。
 */

const LUNAR_INFO = [
  0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,
  0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,
  0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,
  0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,
  0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,
  0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,
  0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,
  0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b6a0, 0x195a6,
  0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,
  0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,
  0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,
  0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,
  0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,
  0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,
  0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,
  0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,
  0x0a2e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,
  0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,
  0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,
  0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,
  0x0d520,
]

const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
const ZODIAC = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']
const MONTH_NAMES = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊']
const DAY_NAMES = [
  '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
  '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
  '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]

const JIAN_CHU = ['建', '除', '满', '平', '定', '执', '破', '危', '成', '收', '开', '闭']

const YI_JI = [
  { yi: ['出行', '上任', '会友', '祈福'], ji: ['动土', '开仓', '安葬'] },
  { yi: ['除旧', '疗病', '扫舍', '祭祀'], ji: ['出行', '嫁娶', '开市'] },
  { yi: ['祭祀', '祈福', '开市', '交易'], ji: ['动土', '安葬', '赴任'] },
  { yi: ['修饰', '平治道涂', '嫁娶'], ji: ['开渠', '栽种', '安葬'] },
  { yi: ['冠笄', '嫁娶', '修造', '入宅'], ji: ['诉讼', '出行', '开仓'] },
  { yi: ['捕捉', '纳畜', '祭祀'], ji: ['开市', '移徙', '出行'] },
  { yi: ['破屋', '坏垣', '求医'], ji: ['嫁娶', '开市', '出行'] },
  { yi: ['安床', '祭祀', '祈福'], ji: ['登高', '行船', '动土'] },
  { yi: ['开市', '嫁娶', '入宅', '出行'], ji: ['诉讼', '安葬'] },
  { yi: ['纳财', '收账', '入仓'], ji: ['开市', '安葬', '出行'] },
  { yi: ['开市', '出行', '求财', '祈福'], ji: ['安葬', '动土'] },
  { yi: ['筑堤', '埋穴', '收藏'], ji: ['开市', '出行', '嫁娶'] },
]

function leapMonth(year) {
  return LUNAR_INFO[year - 1900] & 0xf
}

function leapDays(year) {
  if (!leapMonth(year)) return 0
  return (LUNAR_INFO[year - 1900] & 0x10000) ? 30 : 29
}

function monthDays(year, month) {
  return (LUNAR_INFO[year - 1900] & (0x10000 >> month)) ? 30 : 29
}

function lunarYearDays(year) {
  let sum = 348
  for (let i = 0x8000; i > 0x8; i >>= 1) {
    sum += (LUNAR_INFO[year - 1900] & i) ? 1 : 0
  }
  return sum + leapDays(year)
}

function ganzhiYear(lunarYear) {
  const index = (lunarYear - 4) % 60
  return GAN[index % 10] + ZHI[index % 12]
}

function ganzhiDay(date) {
  const days = Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - Date.UTC(1900, 0, 31)) / 86400000)
  const index = (days + 40) % 60
  return { text: GAN[index % 10] + ZHI[index % 12], zhiIndex: index % 12 }
}

function ganzhiMonth(lunarYear, lunarMonth) {
  const yearStem = ((lunarYear - 4) % 60) % 10
  const monthStem = (yearStem * 2 + lunarMonth + 1) % 10
  const monthZhi = (lunarMonth + 1) % 12
  return { text: GAN[monthStem] + ZHI[monthZhi], zhiIndex: monthZhi }
}

export function solarToLunar(date = new Date()) {
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()

  let offset = Math.floor((Date.UTC(year, month - 1, day) - Date.UTC(1900, 0, 31)) / 86400000)
  let i
  let temp = 0
  for (i = 1900; i < 2101 && offset > 0; i++) {
    temp = lunarYearDays(i)
    offset -= temp
  }
  if (offset < 0) {
    offset += temp
    i--
  }
  const lunarYear = i

  const leap = leapMonth(lunarYear)
  let isLeap = false
  for (i = 1; i < 13 && offset > 0; i++) {
    if (leap > 0 && i === leap + 1 && !isLeap) {
      --i
      isLeap = true
      temp = leapDays(lunarYear)
    } else {
      temp = monthDays(lunarYear, i)
    }
    if (isLeap && i === leap + 1) isLeap = false
    offset -= temp
  }
  if (offset === 0 && leap > 0 && i === leap + 1) {
    if (isLeap) {
      isLeap = false
    } else {
      isLeap = true
      --i
    }
  }
  if (offset < 0) {
    offset += temp
    --i
  }

  const lunarMonth = i
  const lunarDay = offset + 1
  const dayGz = ganzhiDay(date)
  const monthGz = ganzhiMonth(lunarYear, lunarMonth)
  const jianChuIndex = (dayGz.zhiIndex - monthGz.zhiIndex + 12) % 12

  return {
    lunarYear,
    lunarMonth,
    lunarDay,
    isLeap,
    monthText: (isLeap ? '闰' : '') + MONTH_NAMES[lunarMonth - 1] + '月',
    dayText: DAY_NAMES[lunarDay - 1],
    yearGanZhi: ganzhiYear(lunarYear),
    monthGanZhi: monthGz.text,
    dayGanZhi: dayGz.text,
    zodiac: ZODIAC[((lunarYear - 4) % 60) % 12],
    jianChu: JIAN_CHU[jianChuIndex],
    yi: YI_JI[jianChuIndex].yi,
    ji: YI_JI[jianChuIndex].ji,
  }
}

export default { solarToLunar }
