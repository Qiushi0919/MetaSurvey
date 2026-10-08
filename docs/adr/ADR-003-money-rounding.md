# ADR-003 money / Decimal / rounding 规范

状态：P0 工程规范实现，待 Gate Review；真实券商结算需单独核验。

决定：金额 wire 为最多 38 位整数分字符串，计算用 BigInt；价格/费率为精确 Decimal 字符串，禁止 float 金额、指数、NaN、隐式类型转换。费用基线使用私有 100 位 Decimal 构造器，各组件 HALF_UP 到分后求和；BigInt oracle 独立复算。量为 safe integer 股数。

SQL 使用无 typmod 的 NUMERIC domain，以 CHECK 拒绝小数分和超精度；不能用 NUMERIC(38,0) 静默舍入输入。价格最多 14 位整数/6dp，通用 Decimal 最多 10 位整数/10dp。

显式含费预算用于 affordableQty；最低佣金边界必须测试。滑点已含执行价时额外滑点金额为零。PER_ORDER 完整模拟订单是 P0 harness 的限制，不代表真实部分成交/撤单结算规则。费率、最低佣金、包含项、生效日期、来源和真实舍入政策均不得从实验继承。
