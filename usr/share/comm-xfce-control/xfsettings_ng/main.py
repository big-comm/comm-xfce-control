# -*- coding: utf-8 -*-
"""
Ponto de entrada da aplicação XFSettings NG.
Exibe um dashboard híbrido que lança apps de configuração do XFCE e
também navega para módulos de configuração internos.
"""
import sys
import subprocess
import shlex
import gettext
import locale
from pathlib import Path
from .backend.desktop_files_manager import DesktopFilesManager

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import (
    Gtk, Adw, GLib, Pango,
    Gdk, GObject, Gio
)

APP_ID = "comm.big.xfce-control-center"
LOCALE_DIR = "/usr/share/locale"

locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain(APP_ID, LOCALE_DIR)
gettext.textdomain(APP_ID)
_ = gettext.gettext


class LauncherCard(Gtk.Button):
    """Um widget de "cartão" clicável para cada item do dashboard."""
    def __init__(self, app_info: dict):
        super().__init__()
        self.app_info = app_info
        self.set_css_classes(["card"])
        self.set_size_request(100, 100)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.set_valign(Gtk.Align.START)

        # Cria o tooltip com as informações completas
        tooltip_text = f'{app_info["name"]}\n\n{app_info["comment"]}'
        self.set_tooltip_text(tooltip_text)

        # Container vertical para organizar o conteúdo do cartão
        vbox = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6,
            margin_top=12, margin_bottom=12, margin_start=12, margin_end=12
        )

        icon = Gtk.Image.new_from_icon_name(app_info["icon"])
        icon.set_icon_size(Gtk.IconSize.LARGE)

        # Título do cartão, com uma única linha e "..." se for longo
        name_label = Gtk.Label()
        name_label.set_label(app_info["name"])
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_wrap(True)
        name_label.set_max_width_chars(20)
        name_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        name_label.set_lines(1)
        name_label.set_justify(Gtk.Justification.CENTER)
        name_label.add_css_class("title-4")

        # Descrição do cartão, com até 2 linhas
        comment_label = Gtk.Label(label=app_info["comment"])
        comment_label.add_css_class("caption")
        comment_label.set_wrap(True)
        comment_label.set_max_width_chars(20)
        comment_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        comment_label.set_lines(1)
        comment_label.set_ellipsize(Pango.EllipsizeMode.END)
        comment_label.set_justify(Gtk.Justification.CENTER)

        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=3,
            valign=Gtk.Align.END,
            vexpand=True
        )
        text_box.append(name_label)
        text_box.append(comment_label)

        vbox.append(icon)
        vbox.append(text_box)

        self.set_child(vbox)


class XFSettingsNGWindow(Adw.ApplicationWindow):
    """A janela principal da aplicação."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("XFCE Control Panel"))
        self.set_default_size(900, 600)
        self.set_icon_name("org.xfce.settings.manager")

        # Guardamos referências que precisaremos mais tarde
        self.search_entry = None
        self.flowboxes = []
        self.view_stack = None

        # O Adw.NavigationView gerencia a pilha de páginas
        self.nav_view = Adw.NavigationView()
        self.set_content(self.nav_view)

        # Cria a página inicial (Dashboard) e a exibe
        dashboard_page = self._create_dashboard_page()
        self.nav_view.push(dashboard_page)

    def _create_dashboard_page(self):
        """Cria e retorna o widget completo da página do dashboard."""
        # Container principal da página do dashboard
        page_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        toolbar_view = Adw.ToolbarView.new()
        toolbar_view.set_content(page_vbox)

        header = Adw.HeaderBar.new()
        toolbar_view.add_top_bar(header)

        search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("search-changed", self._on_search_changed)
        search_bar.set_child(self.search_entry)

        search_button = Gtk.ToggleButton(
            icon_name="system-search-symbolic", tooltip_text=_("Search")
        )
        header.pack_end(search_button)
        search_button.bind_property(
            "active", search_bar, "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL
        )
        page_vbox.append(search_bar)

        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)

        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(self.view_stack)

        switcher_bar = Adw.HeaderBar.new()
        switcher_bar.set_title_widget(view_switcher)
        switcher_bar.set_show_end_title_buttons(False)
        page_vbox.append(switcher_bar)
        page_vbox.append(self.view_stack)

        self.populate_dashboard(self.view_stack)

        dashboard_nav_page = Adw.NavigationPage.new(
            toolbar_view, _("XFCE Control Panel")
        )

        return dashboard_nav_page

    def populate_dashboard(self, main_box: Gtk.Box):
        """Busca os apps, cria as seções e adiciona os módulos internos."""
        manager = DesktopFilesManager()
        grouped_apps = manager.get_xfce_settings_apps()

        category_titles = {
            "big": _("BigLinux"),
            "personal": _("Personal"),
            "hardware": _("Hardware"),
            "system": _("System"),
            "other": _("Others")
        }

        category_icons = {
            "big": "biglinux-blue",
            "personal": "preferences-desktop-personal-symbolic",
            "hardware": "drive-harddisk-symbolic",
            "system": "preferences-system-symbolic",
            "other": "applications-other-symbolic"
        }

        # Cria uma seção para cada categoria de aplicativo
        for category, apps in grouped_apps.items():
            if not apps:
                continue

            # O FlowBox conterá os cartões
            flowbox = Gtk.FlowBox(
                homogeneous=True, selection_mode=Gtk.SelectionMode.NONE,
                max_children_per_line=3, min_children_per_line=3,
                margin_top=24, margin_bottom=24, margin_start=24, margin_end=24
            )
            flowbox.set_filter_func(self._filter_func)

            self.flowboxes.append(flowbox)

            for app_info in apps:
                card = LauncherCard(app_info)
                card.connect("clicked", self.on_card_clicked)
                flowbox.append(card)

            # Cada página precisa de rolagem individual
            scrolled_window = Gtk.ScrolledWindow(vexpand=True)
            scrolled_window.set_policy(
                Gtk.PolicyType.NEVER,
                Gtk.PolicyType.AUTOMATIC
            )
            scrolled_window.set_child(flowbox)

            # Adiciona a página com rolagem ao ViewStack
            # O ViewSwitcher usará o título para criar o botão da aba
            page = self.view_stack.add_titled_with_icon(
                scrolled_window,
                category,
                category_titles.get(category, _("Unknown")),
                category_icons.get(category, "dialog-question-symbolic")
            )

            flowbox.page_reference = page

    def on_card_clicked(self, card: LauncherCard):
        """Executa o comando do app."""
        app_info = card.app_info

        # executa o comando do lançador
        exec_string = app_info["exec"]
        command_base = exec_string.split('%')[0].strip()
        command_args = shlex.split(command_base)
        try:
            subprocess.Popen(command_args)
        except Exception as e:
            print(e)

    def _on_search_changed(self, search_entry):
        """
        Chamado sempre que o texto da busca muda.
        Agora com lógica para encontrar a primeira aba com resultados.
        """
        search_text = search_entry.get_text().lower()

        # Primeiro, força a refiltragem visual de todas as abas
        for flowbox in self.flowboxes:
            flowbox.invalidate_filter()

        # Se a busca não está ativa, não precisamos fazer mais nada
        if not search_text:
            return

        # Agora, procuramos qual aba deve ser a visível
        found_in_page = None
        for flowbox in self.flowboxes:
            # Iteramos por todos os filhos do flowbox para verificar a condição
            child = flowbox.get_child_at_index(0)
            while child:
                card = child.get_child()
                app_name = card.app_info["name"].lower()
                app_comment = card.app_info["comment"].lower()

                # Se encontrarmos um cartão que corresponde à busca
                if search_text in app_name or search_text in app_comment:
                    # Guardamos a referência da página e paramos a busca
                    found_in_page = flowbox.page_reference
                    break

                child = child.get_next_sibling()

            if found_in_page:
                break

        # Se encontramos um resultado, mudamos para a aba correspondente
        if found_in_page:
            self.view_stack.set_visible_child_name(found_in_page.get_name())

    def _filter_func(self, flowbox_child) -> bool:
        """Função de filtro para os cartões."""
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True

        card = flowbox_child.get_child()
        app_name = card.app_info["name"].lower()
        app_comment = card.app_info["comment"].lower()

        return search_text in app_name or search_text in app_comment


class XFCEControlCenterApp(Adw.Application):
    """A classe da aplicação principal."""
    def __init__(self, **kwargs):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('activate', self.on_activate)
        self.win = None

    def on_activate(self, app):
        if not self.win:
            self.win = XFSettingsNGWindow(application=app)

        self.win.present()


def main():
    """Ponto de entrada do programa."""
    GLib.set_prgname(APP_ID)
    app = XFCEControlCenterApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
