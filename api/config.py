"""MCP Tool Hub — 插件配置字段与模型定义

插件通过 ConfigField 类属性声明配置项，ConfigModel 收集字段。
框架自动从数据库加载/保存配置，前端自动生成配置界面。

插件可继承 ConfigField 重写 create_widget() 实现自定义控件::

    class ColorField(StringField):
        widget_type = "color"

        def create_widget(self, parent=None):
            return ColorPickerWidget(self.default, parent)

配置模型继承可覆盖字段::

    class BaseHttpConfig(ConfigModel):
        timeout = IntField(default=30, label="超时(秒)")

    class MyConfig(BaseHttpConfig):
        timeout = IntField(default=60, label="超时(秒)")  # 覆盖
        api_key = StringField(default="", label="API Key")  # 新增
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable, ClassVar, Generic, TypeVar, overload

T = TypeVar("T")


# ── 配置控件协议 ──


class ConfigWidgetBase:
    """
    配置控件协议

    所有 create_widget() 返回的对象必须实现：
    - get_value() -> Any：获取当前值
    - set_value(value) -> None：设置当前值

    Qt 实现通常同时继承 QWidget，并添加 value_change 信号。
    """

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError


# ── 配置字段基类 ──


class ConfigField(Generic[T]):
    """
    配置字段基类

    子类通过类名决定 UI 类型，变量名作为配置 key。
    插件可继承并重写 create_widget() 实现自定义控件。

    Attributes:
        default: 默认值
        label: 显示标签
        description: tooltip 提示
        visible: 是否在 UI 中展示（默认 True，设为 False 可隐藏）
        validator: 自定义验证函数

    Class attributes:
        widget_type: UI 控件类型标识，由工厂使用
    """

    widget_type: ClassVar[str] = "base"

    def __init__(
        self,
        default: T,
        label: str = "",
        description: str = "",
        visible: bool = True,
        validator: Callable[[T], bool] | None = None,
    ) -> None:
        self.default = default
        self.label = label
        self.description = description
        self.visible = visible
        self.validator = validator
        self._name: str = ""  # set by __set_name__

    def __set_name__(self, owner, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type) -> ConfigField[T]: ...
    @overload
    def __get__(self, instance: Any, owner: type) -> T: ...

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance._data.get(self._name, self.default)

    def __set__(self, instance, value: T) -> None:
        instance._data[self._name] = value

    @abstractmethod
    def create_widget(self, parent: Any = None) -> ConfigWidgetBase:
        """创建配置控件（仅前端调用，后端不调用此方法）

        插件可重写此方法实现自定义控件。
        """
        pass

    def to_storage(self, value: T) -> Any:
        """转换为存储格式（JSON 可序列化）"""
        return value

    def from_storage(self, data: Any) -> T:
        """从存储格式恢复"""
        return data  # type: ignore

    def validate_value(self, value: T) -> bool:
        """验证值是否有效"""
        if self.validator is not None:
            return self.validator(value)
        return True


# ── 内置字段类型 ──


class StringField(ConfigField[str]):
    """文本字段"""

    widget_type = "string"

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, LineEdit

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._edit = LineEdit()
                self._edit.setText(str(field.default))
                if field.description:
                    self._edit.setToolTip(field.description)
                self._edit.textChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._edit, 1)

            def get_value(self) -> str:
                return self._edit.text()

            def set_value(self, value: str) -> None:
                self._edit.setText(str(value) if value is not None else "")

        return _Widget(parent)

    def to_storage(self, value: str) -> str:
        return value

    def from_storage(self, data: Any) -> str:
        return str(data) if data is not None else ""


class PasswordField(ConfigField[str]):
    """密码字段"""

    widget_type = "password"

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, PasswordLineEdit

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._edit = PasswordLineEdit()
                self._edit.setText(str(field.default))
                if field.description:
                    self._edit.setToolTip(field.description)
                self._edit.textChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._edit, 1)

            def get_value(self) -> str:
                return self._edit.text()

            def set_value(self, value: str) -> None:
                self._edit.setText(str(value) if value is not None else "")

        return _Widget(parent)

    def to_storage(self, value: str) -> str:
        return value

    def from_storage(self, data: Any) -> str:
        return str(data) if data is not None else ""


class IntField(ConfigField[int]):
    """整数字段"""

    widget_type = "int"

    def __init__(
        self,
        default: int = 0,
        label: str = "",
        description: str = "",
        visible: bool = True,
        validator: Callable[[int], bool] | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> None:
        super().__init__(default, label, description, visible, validator)
        self.min_value = min_value
        self.max_value = max_value

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, SpinBox

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._spin = SpinBox()
                self._spin.setValue(field.default)
                if field.min_value is not None:
                    self._spin.setMinimum(field.min_value)
                if field.max_value is not None:
                    self._spin.setMaximum(field.max_value)
                if field.description:
                    self._spin.setToolTip(field.description)
                self._spin.valueChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._spin, 1)

            def get_value(self) -> int:
                return self._spin.value()

            def set_value(self, value: int) -> None:
                self._spin.setValue(int(value) if value is not None else 0)

        return _Widget(parent)

    def to_storage(self, value: int) -> int:
        return value

    def from_storage(self, data: Any) -> int:
        return int(data) if data is not None else 0


class FloatField(ConfigField[float]):
    """浮点数字段"""

    widget_type = "float"

    def __init__(
        self,
        default: float = 0.0,
        label: str = "",
        description: str = "",
        visible: bool = True,
        validator: Callable[[float], bool] | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        decimals: int = 2,
    ) -> None:
        super().__init__(default, label, description, visible, validator)
        self.min_value = min_value
        self.max_value = max_value
        self.decimals = decimals

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, DoubleSpinBox

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._spin = DoubleSpinBox()
                self._spin.setDecimals(field.decimals)
                self._spin.setValue(field.default)
                if field.min_value is not None:
                    self._spin.setMinimum(field.min_value)
                if field.max_value is not None:
                    self._spin.setMaximum(field.max_value)
                if field.description:
                    self._spin.setToolTip(field.description)
                self._spin.valueChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._spin, 1)

            def get_value(self) -> float:
                return self._spin.value()

            def set_value(self, value: float) -> None:
                self._spin.setValue(float(value) if value is not None else 0.0)

        return _Widget(parent)

    def to_storage(self, value: float) -> float:
        return value

    def from_storage(self, data: Any) -> float:
        return float(data) if data is not None else 0.0


class BoolField(ConfigField[bool]):
    """布尔字段"""

    widget_type = "bool"

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, CheckBox

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._check = CheckBox()
                self._check.setChecked(bool(field.default))
                if field.description:
                    self._check.setToolTip(field.description)
                self._check.toggled.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._check, 1)

            def get_value(self) -> bool:
                return self._check.isChecked()

            def set_value(self, value: bool) -> None:
                self._check.setChecked(bool(value))

        return _Widget(parent)

    def to_storage(self, value: bool) -> bool:
        return value

    def from_storage(self, data: Any) -> bool:
        return bool(data) if data is not None else False


class ChoiceField(ConfigField[str]):
    """下拉选择字段"""

    widget_type = "choice"

    def __init__(
        self,
        default: str = "",
        choices: list[str] | None = None,
        label: str = "",
        description: str = "",
        visible: bool = True,
        validator: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__(default, label, description, visible, validator)
        self.choices = choices or []

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, ComboBox

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._combo = ComboBox()
                self._combo.addItems(field.choices)
                if field.default in field.choices:
                    self._combo.setCurrentText(field.default)
                if field.description:
                    self._combo.setToolTip(field.description)
                self._combo.currentTextChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._combo, 1)

            def get_value(self) -> str:
                return self._combo.currentText()

            def set_value(self, value: str) -> None:
                self._combo.setCurrentText(str(value) if value else "")

        return _Widget(parent)

    def to_storage(self, value: str) -> str:
        return value

    def from_storage(self, data: Any) -> str:
        return str(data) if data is not None else ""


class PathField(ConfigField[str]):
    """路径选择字段"""

    widget_type = "path"

    def __init__(
        self,
        default: str = "",
        label: str = "",
        description: str = "",
        visible: bool = True,
        validator: Callable[[str], bool] | None = None,
        is_folder: bool = False,
    ) -> None:
        super().__init__(default, label, description, visible, validator)
        self.is_folder = is_folder

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, LineEdit, PushButton, FluentIcon

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)
                self._edit = LineEdit()
                self._edit.setText(str(field.default))
                self._edit.setClearButtonEnabled(True)
                if field.description:
                    self._edit.setToolTip(field.description)
                self._edit.textChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._edit, 1)

                btn = PushButton(FluentIcon.FOLDER, "浏览")
                btn.setFixedWidth(60)
                btn.clicked.connect(self._browse)
                layout.addWidget(btn)

            def _browse(self) -> None:
                from PySide6.QtWidgets import QFileDialog

                if field.is_folder:
                    path = QFileDialog.getExistingDirectory(self, "选择目录")
                else:
                    path, _ = QFileDialog.getOpenFileName(self, "选择文件")
                if path:
                    self._edit.setText(path)

            def get_value(self) -> str:
                return self._edit.text()

            def set_value(self, value: str) -> None:
                self._edit.setText(str(value) if value is not None else "")

        return _Widget(parent)

    def to_storage(self, value: str) -> str:
        return value

    def from_storage(self, data: Any) -> str:
        return str(data) if data is not None else ""


# ── 配置模型 ──


class ConfigModel:
    """
    插件配置声明基类

    用法::

        class HttpToolConfig(ConfigModel):
            api_key = StringField(default="", label="API Key")
            timeout = IntField(default=30, label="超时(秒)")
            use_ssl = BoolField(default=True, label="启用SSL")

    框架自动：
    - get_fields() 收集所有 ConfigField 类属性（MRO 遍历，子类覆盖父类）
    - load_dict() / to_dict() 处理数据库序列化
    - create_form() 自动生成配置界面

    插件通过 descriptor 协议直接读写::

        config.api_key       # 读取
        config.timeout = 60  # 写入
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}  # 当前值

    # ── 字段发现（与 ToolDef 发现模式一致）──

    _fields_cache: dict[str, ConfigField] | None

    @classmethod
    def get_fields(cls) -> dict[str, ConfigField]:
        """自动发现所有 ConfigField 类属性

        遍历类 MRO，子类同名字段覆盖父类。
        """
        if hasattr(cls, "_fields_cache") and cls._fields_cache is not None:
            return cls._fields_cache

        fields: dict[str, ConfigField] = {}
        # 反向 MRO 遍历，让子类覆盖父类
        for klass in reversed(cls.__mro__):
            for name, attr in vars(klass).items():
                if isinstance(attr, ConfigField):
                    fields[name] = attr

        cls._fields_cache = fields  # type: ignore[assignment]
        return fields

    # ── 序列化 ──

    def load_dict(self, data: dict[str, Any]) -> None:
        """从 dict 加载配置（数据库 JSON 反序列化后调用）

        只加载字段声明中存在的 key，忽略未知 key。
        """
        fields = self.get_fields()
        for name, field in fields.items():
            if name in data:
                self._data[name] = field.from_storage(data[name])
            else:
                self._data[name] = field.default

    def to_dict(self) -> dict[str, Any]:
        """导出为 dict（JSON 可序列化，写入数据库）"""
        fields = self.get_fields()
        result: dict[str, Any] = {}
        for name, field in fields.items():
            value = self._data.get(name, field.default)
            result[name] = field.to_storage(value)
        return result

    # ── 验证 ──

    def validate_all(self) -> dict[str, bool]:
        """验证所有字段，返回 {field_name: is_valid}"""
        fields = self.get_fields()
        result: dict[str, bool] = {}
        for name, field in fields.items():
            value = self._data.get(name, field.default)
            result[name] = field.validate_value(value)
        return result

    # ── 配置界面 ──

    def create_form(self, parent: Any = None) -> Any:
        """自动生成配置表单 QWidget

        为每个 visible=True 的字段调用 create_widget()，
        垂直排列，返回包含所有字段的 QWidget。

        调用方可以获取表单值::

            form = config.create_form(parent)
            # ... 展示给用户
            values = form.get_values()  # 获取所有字段当前值
            form.set_values(data)       # 批量设置值
        """
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        from qfluentwidgets import StrongBodyLabel

        model = self

        class _ConfigForm(QWidget):
            config_changed = Signal(object)  # 任意字段变化时发射

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(12)

                self._field_widgets: dict[str, ConfigWidgetBase] = {}

                for name, field in model.get_fields().items():
                    if not field.visible:
                        continue

                    # 分组标题（如果 description 较长，作为分隔提示）
                    widget = field.create_widget(self)
                    self._field_widgets[name] = widget

                    # 连接字段变化信号
                    if hasattr(widget, "value_change"):
                        widget.value_change.connect(  # type: ignore[union-attr]
                            lambda v, n=name: self.config_changed.emit({n: v})
                        )

                    layout.addWidget(widget)  # type: ignore[arg-type]

                layout.addStretch()

            def get_values(self) -> dict[str, Any]:
                """获取所有字段当前值（经 to_storage 序列化）"""
                result = {}
                for name, widget in self._field_widgets.items():
                    raw = widget.get_value()
                    field = model.get_fields().get(name)
                    result[name] = field.to_storage(raw) if field else raw
                return result

            def set_values(self, data: dict[str, Any]) -> None:
                """批量设置字段值"""
                for name, value in data.items():
                    if name in self._field_widgets:
                        self._field_widgets[name].set_value(value)

        return _ConfigForm(parent)
