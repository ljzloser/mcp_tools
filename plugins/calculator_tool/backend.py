"""MCP Tool Hub — 数学计算插件

基于 sympy / pendulum / pint，提供常用的数学计算、日期计算、单位换算能力。

工具：
  - calc_eval:          计算表达式
  - calc_solve:         解方程
  - calc_simplify:      化简表达式
  - calc_diff:          求导
  - calc_integrate:     积分
  - calc_matrix:        矩阵运算
  - calc_convert_base:  进制转换
  - calc_date:          日期计算
  - calc_unit:          单位换算
"""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


class EvalArgs(BaseModel):
    """计算表达式"""

    expression: str = Field(description="数学表达式，如 2**10 + sin(pi/4)")


class SolveArgs(BaseModel):
    """解方程"""

    equation: str = Field(description="方程，如 x**2 - 4 = 0 或 x**2 - 4")
    variable: str = Field(default="x", description="未知数符号，默认 x")


class SimplifyArgs(BaseModel):
    """化简表达式"""

    expression: str = Field(description="要化简的表达式，如 (x+1)**2")


class DiffArgs(BaseModel):
    """求导"""

    expression: str = Field(description="表达式，如 sin(x)**2")
    variable: str = Field(default="x", description="求导变量，默认 x")


class IntegrateArgs(BaseModel):
    """积分"""

    expression: str = Field(description="被积表达式，如 x**2")
    variable: str = Field(default="x", description="积分变量，默认 x")
    lower: str = Field(default="", description="下限（留空则求不定积分）")
    upper: str = Field(default="", description="上限")


class MatrixArgs(BaseModel):
    """矩阵运算"""

    matrix: str = Field(description="矩阵，如 [[1,2],[3,4]]")
    operation: str = Field(
        default="det",
        description="运算: det(行列式), inv(逆矩阵), T(转置), eigenvects(特征值), rref(行最简)",
    )


class ConvertBaseArgs(BaseModel):
    """进制转换"""

    value: str = Field(description="数值，如 255, 0xFF, 0b1010, 0o17")
    to_base: str = Field(default="", description="目标进制: 2/8/10/16 或 bin/oct/dec/hex（留空则全部输出）")


class DateArgs(BaseModel):
    """日期计算"""

    expression: str = Field(
        description="日期表达式，如: now, 2025-01-01, now+3d, 2025-01-01 to 2025-12-31",
    )


class UnitArgs(BaseModel):
    """单位换算"""

    value: float = Field(description="数值")
    from_unit: str = Field(description="源单位，如 km, kg, °C")
    to_unit: str = Field(description="目标单位，如 m, lb, °F")


# ── 插件实现 ──


class CalculatorToolPlugin(BasePlugin):
    """数学计算插件"""

    calc_eval = ToolDef("calc_eval", EvalArgs, description="计算数学表达式，支持加减乘除、幂、三角函数、对数等")
    calc_solve = ToolDef("calc_solve", SolveArgs, description="解方程（支持多项式、超越方程）")
    calc_simplify = ToolDef("calc_simplify", SimplifyArgs, description="化简数学表达式")
    calc_diff = ToolDef("calc_diff", DiffArgs, description="对表达式求导")
    calc_integrate = ToolDef("calc_integrate", IntegrateArgs, description="计算积分（定积分或不定积分）")
    calc_matrix = ToolDef("calc_matrix", MatrixArgs, description="矩阵运算（行列式、逆矩阵、转置、特征值等）")
    calc_convert_base = ToolDef("calc_convert_base", ConvertBaseArgs, description="进制转换（二进制/八进制/十进制/十六进制）")
    calc_date = ToolDef("calc_date", DateArgs, description="日期计算（当前时间、日期加减、时间差）")
    calc_unit = ToolDef("calc_unit", UnitArgs, description="单位换算（长度/质量/温度/面积/体积等）")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="calculator_tool",
            display_name="万能计算器",
            version="1.0.0",
            description="数学计算 / 进制转换 / 日期计算 / 单位换算",
            author="MCP Tool Hub",
            icon="🔢",
        )

    def _eval(self, expr: str):
        """安全求值 sympy 表达式"""
        import sympy
        return sympy.sympify(expr, evaluate=False)

    async def handle_calc_eval(self, args: EvalArgs) -> MCPToolResult:
        try:
            import sympy
            result = sympy.sympify(args.expression)
            # 尝试数值化
            try:
                num = float(result.evalf())
                text = f"{result} = {num}"
            except (TypeError, ValueError):
                text = str(result)
            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"计算失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_solve(self, args: SolveArgs) -> MCPToolResult:
        try:
            import sympy
            x = sympy.Symbol(args.variable)
            eq = args.equation.strip()

            if "=" in eq:
                lhs, rhs = eq.split("=", 1)
                expr = sympy.sympify(f"({lhs}) - ({rhs})")
            else:
                expr = sympy.sympify(eq)

            solutions = sympy.solve(expr, x)
            eq_display = args.equation if "=" in args.equation else f"{args.equation} = 0"
            text = f"方程: {eq_display}\n解: {solutions}"
            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"求解失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_simplify(self, args: SimplifyArgs) -> MCPToolResult:
        try:
            import sympy
            expr = sympy.sympify(args.expression)
            result = sympy.simplify(expr)
            text = f"原式: {args.expression}\n化简: {result}"
            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"化简失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_diff(self, args: DiffArgs) -> MCPToolResult:
        try:
            import sympy
            expr = sympy.sympify(args.expression)
            x = sympy.Symbol(args.variable)
            result = sympy.diff(expr, x)
            text = f"f({args.variable}) = {args.expression}\nf'({args.variable}) = {result}"
            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"求导失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_integrate(self, args: IntegrateArgs) -> MCPToolResult:
        try:
            import sympy
            expr = sympy.sympify(args.expression)
            x = sympy.Symbol(args.variable)

            if args.lower and args.upper:
                lo = sympy.sympify(args.lower)
                hi = sympy.sympify(args.upper)
                result = sympy.integrate(expr, (x, lo, hi))
                text = f"∫({args.expression}) d{args.variable} 从 {lo} 到 {hi}\n= {result}"
            else:
                result = sympy.integrate(expr, x)
                text = f"∫({args.expression}) d{args.variable}\n= {result} + C"

            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"积分失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_matrix(self, args: MatrixArgs) -> MCPToolResult:
        try:
            import sympy
            mat = sympy.sympify(args.matrix)
            # 如果是 Python list，转为 sympy Matrix
            if isinstance(mat, list):
                mat = sympy.Matrix(mat)
            if not isinstance(mat, sympy.Matrix):
                return MCPToolResult(
                    content=[{"type": "text", "text": "输入不是有效矩阵，格式如 [[1,2],[3,4]]"}],
                    is_error=True,
                )

            op = args.operation.lower()
            if op == "det":
                result = f"行列式 = {mat.det()}"
            elif op == "inv":
                result = f"逆矩阵 =\n{mat.inv()}"
            elif op == "t":
                result = f"转置 =\n{mat.T}"
            elif op == "eigenvects":
                ev = mat.eigenvects()
                parts = []
                for val, mult, vecs in ev:
                    parts.append(f"特征值 {val} (重数 {mult}): {vecs[0] if vecs else '无'}")
                result = "特征值分解:\n" + "\n".join(parts)
            elif op == "rref":
                rref_mat, pivots = mat.rref()
                result = f"行最简形 =\n{rref_mat}\n主元列: {pivots}"
            else:
                return MCPToolResult(
                    content=[{"type": "text", "text": f"不支持的运算: {op}\n支持: det, inv, T, eigenvects, rref"}],
                    is_error=True,
                )

            return MCPToolResult(content=[{"type": "text", "text": result}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"矩阵运算失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_convert_base(self, args: ConvertBaseArgs) -> MCPToolResult:
        try:
            value = args.value.strip()
            # 识别输入进制
            if value.startswith("0x") or value.startswith("0X"):
                n = int(value, 16)
            elif value.startswith("0b") or value.startswith("0B"):
                n = int(value, 2)
            elif value.startswith("0o") or value.startswith("0O"):
                n = int(value, 8)
            else:
                n = int(value)

            to = args.to_base.lower().strip()
            bases = {
                "2": (2, "二进制"), "bin": (2, "二进制"),
                "8": (8, "八进制"), "oct": (8, "八进制"),
                "10": (10, "十进制"), "dec": (10, "十进制"),
                "16": (16, "十六进制"), "hex": (16, "十六进制"),
            }

            if to and to in bases:
                base, name = bases[to]
                if base == 2:
                    result = f"二进制: {bin(n)}"
                elif base == 8:
                    result = f"八进制: {oct(n)}"
                elif base == 10:
                    result = f"十进制: {n}"
                elif base == 16:
                    result = f"十六进制: {hex(n)}"
            else:
                result = (
                    f"十进制: {n}\n"
                    f"二进制: {bin(n)}\n"
                    f"八进制: {oct(n)}\n"
                    f"十六进制: {hex(n)}"
                )

            return MCPToolResult(content=[{"type": "text", "text": result}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"进制转换失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_date(self, args: DateArgs) -> MCPToolResult:
        try:
            import pendulum

            expr = args.expression.strip().lower()

            # 当前时间
            if expr in ("now", "now()", "当前时间", "今天"):
                now = pendulum.now()
                text = (
                    f"当前时间: {now.format('YYYY-MM-DD HH:mm:ss')}\n"
                    f"星期: {now.format('dddd')}\n"
                    f"时间戳: {int(now.timestamp())}"
                )
                return MCPToolResult(content=[{"type": "text", "text": text}])

            # 时间差计算: date1 to date2
            if " to " in expr or " 到 " in expr:
                sep = " to " if " to " in expr else " 到 "
                parts = expr.split(sep)
                d1 = pendulum.parse(parts[0].strip(), exact=True)
                d2 = pendulum.parse(parts[1].strip(), exact=True)
                diff = abs(d2.diff(d1))
                text = (
                    f"{d1.format('YYYY-MM-DD')} → {d2.format('YYYY-MM-DD')}\n"
                    f"相差: {diff.in_days()} 天\n"
                    f"      {diff.in_hours()} 小时\n"
                    f"      {diff.in_minutes()} 分钟"
                )
                return MCPToolResult(content=[{"type": "text", "text": text}])

            # 日期加减: now+3d, 2025-01-01+7d, now+1y2m3d
            import re
            m = re.match(r"^(.+?)\s*([+-]\s*\d+\s*[yMdHhms]+(?:[+-]?\s*\d+\s*[yMdHhms]+)*)$", expr)
            if m:
                base_str = m.group(1).strip()
                delta_str = m.group(2).strip()

                if base_str in ("now", "now()", "当前时间", "今天"):
                    base = pendulum.now()
                else:
                    # 先尝试直接解析，如果失败则去掉空格再试
                    try:
                        base = pendulum.parse(base_str, exact=True)
                    except Exception:
                        base = pendulum.parse(base_str.replace(" ", ""), exact=True)
                    # Date → DateTime（确保可加减时间）
                    if isinstance(base, pendulum.Date) and not isinstance(base, pendulum.DateTime):
                        base = pendulum.datetime(base.year, base.month, base.day)

                # 解析增量
                units = {"y": "years", "m": "months", "d": "days", "h": "hours", "min": "minutes", "s": "seconds"}
                deltas = re.findall(r"([+-]?\s*\d+)\s*([yMdHhms]+)", delta_str)
                add_kwargs = {}
                sub_kwargs = {}
                for val, unit in deltas:
                    key = units.get(unit.rstrip("s"), unit)
                    num = int(val.replace(" ", ""))
                    if num >= 0:
                        add_kwargs[key] = num
                    else:
                        sub_kwargs[key] = -num

                result = base
                if add_kwargs:
                    result = result.add(**add_kwargs)
                if sub_kwargs:
                    result = result.subtract(**sub_kwargs)

                text = f"{base.format('YYYY-MM-DD HH:mm:ss')} {delta_str}\n= {result.format('YYYY-MM-DD HH:mm:ss')}\n星期: {result.format('dddd')}"
                return MCPToolResult(content=[{"type": "text", "text": text}])

            # 单纯解析日期
            d = pendulum.parse(expr, exact=True)
            text = f"日期: {d.format('YYYY-MM-DD HH:mm:ss')}\n星期: {d.format('dddd')}\n时间戳: {int(d.timestamp())}"
            return MCPToolResult(content=[{"type": "text", "text": text}])

        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"日期计算失败: {e}"}],
                is_error=True,
            )

    async def handle_calc_unit(self, args: UnitArgs) -> MCPToolResult:
        try:
            from pint import UnitRegistry
            ureg = UnitRegistry()

            # 温度特殊处理
            from_unit = args.from_unit.strip().lower()
            to_unit = args.to_unit.strip().lower()

            temp_map = {
                "c": "celsius", "°c": "celsius", "℃": "celsius",
                "f": "fahrenheit", "°f": "fahrenheit", "℉": "fahrenheit",
                "k": "kelvin", "°k": "kelvin",
            }
            src_is_temp = from_unit in temp_map
            dst_is_temp = to_unit in temp_map

            if src_is_temp or dst_is_temp:
                src_name = temp_map.get(from_unit, from_unit)
                dst_name = temp_map.get(to_unit, to_unit)

                # 使用公式直接转换
                v = args.value
                if src_name == "celsius" and dst_name == "fahrenheit":
                    result = v * 9 / 5 + 32
                    text = f"{v} °C = {result:.2f} °F"
                elif src_name == "fahrenheit" and dst_name == "celsius":
                    result = (v - 32) * 5 / 9
                    text = f"{v} °F = {result:.2f} °C"
                elif src_name == "celsius" and dst_name == "kelvin":
                    result = v + 273.15
                    text = f"{v} °C = {result:.2f} K"
                elif src_name == "kelvin" and dst_name == "celsius":
                    result = v - 273.15
                    text = f"{v} K = {result:.2f} °C"
                elif src_name == "fahrenheit" and dst_name == "kelvin":
                    result = (v - 32) * 5 / 9 + 273.15
                    text = f"{v} °F = {result:.2f} K"
                elif src_name == "kelvin" and dst_name == "fahrenheit":
                    result = (v - 273.15) * 9 / 5 + 32
                    text = f"{v} K = {result:.2f} °F"
                elif src_name == dst_name:
                    text = f"{v} {args.from_unit} = {v} {args.to_unit}"
                else:
                    return MCPToolResult(
                        content=[{"type": "text", "text": f"不支持的温度转换: {args.from_unit} → {args.to_unit}"}],
                        is_error=True,
                    )
            else:
                src = ureg.parse_expression(f"{args.value} {args.from_unit}")
                result = src.to(args.to_unit)
                text = f"{args.value} {args.from_unit} = {result}"

            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"单位换算失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("CalculatorToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("CalculatorToolPlugin 已卸载")
