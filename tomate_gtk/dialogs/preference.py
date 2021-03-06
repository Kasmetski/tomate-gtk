from __future__ import unicode_literals

import locale
import logging
from locale import gettext as _

from gi.repository import GdkPixbuf, Gtk
from wiring import inject, Module, SingletonScope

locale.textdomain('tomate')
logger = logging.getLogger(__name__)


class PreferenceDialog(Gtk.Dialog):

    @inject(duration='view.preference.duration',
            extension='view.preference.extension')
    def __init__(self, duration, extension):
        self.extension = extension
        self.duration = duration

        Gtk.Dialog.__init__(
            self,
            _('Preferences'),
            None,
            buttons=(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE),
            modal=True,
            resizable=False,
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
        )

        self.set_size_request(350, 200)

        self.connect('response', self.on_dialog_response)

        stack = Gtk.Stack()
        stack.add_titled(self.duration, 'timer', _('Timer'))

        scrolledwindow = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.OUT)
        scrolledwindow.add_with_viewport(self.extension)

        stack.add_titled(scrolledwindow, 'extension', _('Extensions'))

        switcher = Gtk.StackSwitcher(margin_top=5,
                                     margin_bottom=5,
                                     halign=Gtk.Align.CENTER)
        switcher.set_stack(stack)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.pack_start(switcher, True, True, 0)
        box.pack_start(separator, True, True, 0)
        box.pack_start(stack, True, True, 0)
        box.show_all()

        content_area = self.get_content_area()
        content_area.add(box)

    @staticmethod
    def on_dialog_response(widget, parameter):
        widget.hide()

    def refresh_plugin(self):
        self.extension.refresh()


class TimerDurationStack(Gtk.Grid):

    @inject(config='tomate.config')
    def __init__(self, config):
        self.config = config

        Gtk.Grid.__init__(
            self,
            column_spacing=6,
            margin_bottom=12,
            margin_left=12,
            margin_right=12,
            margin_top=12,
            row_spacing=6,
        )

        section = self._add_section(_('Duration:'))
        self.attach(section, 0, 0, 1, 1)

        # Pomodoro Duration
        label, setting = self._add_setting(_('Pomodoro:'),
                                           Gtk.SpinButton.new_with_range(1, 99, 1),
                                           'pomodoro_duration')
        self.attach(label, 0, 1, 1, 1)
        self.attach_next_to(setting, label, Gtk.PositionType.RIGHT, 3, 1)

        # Short Break Duration
        label, setting = self._add_setting(_('Short break:'),
                                           Gtk.SpinButton.new_with_range(1, 99, 1),
                                           'shortbreak_duration')
        self.attach(label, 0, 2, 1, 1)
        self.attach_next_to(setting, label, Gtk.PositionType.RIGHT, 3, 1)

        # Long Break Duration
        label, setting = self._add_setting(_('Long Break'),
                                           Gtk.SpinButton.new_with_range(1, 99, 1),
                                           'longbreak_duration')
        self.attach(label, 0, 3, 1, 1)
        self.attach_next_to(setting, label, Gtk.PositionType.RIGHT, 3, 1)

    @staticmethod
    def _add_section(name):
        section = Gtk.Label('<b>{0}</b>'.format(name), use_markup=True)
        section.set_halign(Gtk.Align.START)
        return section

    def _add_setting(self, label_name, spinbutton, option):
        label = Gtk.Label(label_name,
                          margin_left=12,
                          hexpand=True,
                          halign=Gtk.Align.END)

        spinbutton.set_hexpand(True)
        spinbutton.set_halign(Gtk.Align.START)
        spinbutton.set_value(self.config.get_int('Timer', option))
        spinbutton.connect('value-changed', self.on_spinbutton_value_changed, option)

        return label, spinbutton

    def on_spinbutton_value_changed(self, widget, option):
        value = str(widget.get_value_as_int())
        self.config.set('Timer', option, value)


class ExtensionStack(Gtk.TreeView):

    @inject(plugin='tomate.plugin', config='tomate.config')
    def __init__(self, plugin, config):
        self.plugin = plugin
        self.config = config

        Gtk.TreeView.__init__(self, headers_visible=False)

        self.get_selection().set_mode(Gtk.SelectionMode.BROWSE)

        self._store = Gtk.ListStore(bool,  # active
                                    GdkPixbuf.Pixbuf,  # icon
                                    str,   # name
                                    str,   # detail
                                    object)  # plugin

        self.set_model(self._store)

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self.on_plugin_toggled)
        column = Gtk.TreeViewColumn('Active', renderer, active=0)
        self.append_column(column)

        renderer = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn('Icon', renderer, pixbuf=1)
        self.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Detail', renderer, markup=3)
        self.append_column(column)

    def refresh(self):
        self.clear()

        for plugin in self.plugin.getAllPlugins():
            self.add_plugin(plugin)

        if self.there_are_plugins:
            self.select_first_plugin()

    def on_plugin_toggled(self, widget, path):
        plugin = GridPlugin(self._store, path)

        plugin.toggle()

        if plugin.is_enable:
            self.plugin.activatePluginByName(plugin.name)

        else:
            self.plugin.deactivatePluginByName(plugin.name)

    def clear(self):
        self._store.clear()

    def select_first_plugin(self):
        self.get_selection().select_iter(self._store.get_iter_first())

    @property
    def there_are_plugins(self):
        return bool(len(self._store))

    def add_plugin(self, plugin):
        iconname = getattr(plugin, 'icon', 'tomate-plugin')
        iconpath = self.config.get_icon_path(iconname, 16)

        self._store.append((plugin.plugin_object.is_activated,
                            GridPlugin.pixbuf(iconpath),
                            plugin.name,
                            GridPlugin.markup(plugin),
                            plugin))

        logger.debug('plugin %s added', plugin.name)


class GridPlugin(object):

    ACTIVE = 0
    TITLE = 2

    def __init__(self, treestore, treepath):
        treeiter = treestore.get_iter(treepath)
        self._instance = treestore[treeiter]

    @property
    def name(self):
        return self._instance[self.TITLE]

    @property
    def is_enable(self):
        return self._instance[self.ACTIVE]

    def toggle(self):
        self._instance[self.ACTIVE] = not self._instance[self.ACTIVE]

    @staticmethod
    def pixbuf(iconpath):
        return GdkPixbuf.Pixbuf.new_from_file(iconpath)

    @staticmethod
    def markup(plugin):
        return ('<b>{name}</b> ({version})'
                '\n<small>{description}</small>'
                ).format(name=plugin.name,
                         version=plugin.version,
                         description=plugin.description)


class PreferenceDialogModule(Module):
    factories = {
        'view.preference.extension': (ExtensionStack, SingletonScope),
        'view.preference.duration': (TimerDurationStack, SingletonScope),
        'view.preference': (PreferenceDialog, SingletonScope),
    }
