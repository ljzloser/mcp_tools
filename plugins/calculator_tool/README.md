# 数学计算工具

基于 sympy / pendulum / pint 的计算工具集合。

## 工具

### calc_eval — 计算表达式

```
2**10 + sin(pi/4)
sqrt(2) * log(100)
```

### calc_solve — 解方程

```
x**2 - 4 = 0
sin(x) - 0.5 = 0
```

### calc_simplify — 化简

```
(x+1)**2 → x**2 + 2*x + 1
```

### calc_diff — 求导

```
sin(x)**2 → 2*sin(x)*cos(x)
```

### calc_integrate — 积分

```
x**2 → x**3/3 + C
x**2, 0, 1 → 1/3
```

### calc_matrix — 矩阵运算

支持: det / inv / T / eigenvects / rref

### calc_convert_base — 进制转换

```
255 → 十进制/二进制/八进制/十六进制
0xFF → 全部输出
```

### calc_date — 日期计算

```
now              → 当前时间
2025-01-01       → 解析日期
now + 30d        → 日期加减
2025-01-01 to 2025-12-31 → 时间差
```

支持单位: y(年) m(月) d(天) h(时) min(分) s(秒)

### calc_unit — 单位换算

```
100 km → m
72 °F → °C
5 kg → lb
```

支持: 长度 / 质量 / 温度 / 面积 / 体积 / 时间 / 速度 等
