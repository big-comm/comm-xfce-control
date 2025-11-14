# -*- coding: utf-8 -*-
"""
Backend para descobrir e analisar arquivos .desktop de configurações.
"""
import configparser
from pathlib import Path
from typing import List, Dict, TypedDict
import locale

# Os diretórios-base para busca de aplicativos, conforme a especificação XDG.
APP_DIRS = [
    Path("/usr/share/applications/"),
    Path("/usr/local/share/applications/"),
    Path("~/.local/share/applications/").expanduser(),
]


class DesktopAppInfo(TypedDict):
    """Define a estrutura de dados para um aplicativo .desktop analisado."""
    name: str
    comment: str
    icon: str
    exec: str
    id: str


class DesktopFilesManager:
    """
    Encontra, analisa e agrupa os aplicativos de configuração.
    """

    @staticmethod
    def get_xfce_settings_apps() -> Dict[str, List[DesktopAppInfo]]:
        """
        Varre os diretórios XDG, encontra arquivos .desktop de configuração
        e os agrupa por categoria XFCE.
        """
        grouped_apps: Dict[str, List[DesktopAppInfo]] = {
            "big": [],
            "personal": [],
            "hardware": [],
            "system": [],
            "other": [],
        }
        found_ids = set()
        parser = configparser.ConfigParser(interpolation=None)
        # Preserva o case das chaves (ex: 'X-XFCE-PersonalSettings')
        parser.optionxform = str

        try:
            _lang, _ = locale.getlocale()
            _code = _lang.split('_')[0] if _lang else None
        except Exception:
            # Fallback seguro caso o locale não possa ser determinado
            _lang, _code = None, None

        for directory in reversed(APP_DIRS):
            if not directory.is_dir():
                continue

            for desktop_file in directory.glob("**/*.desktop"):
                try:
                    parser.clear()
                    parser.read(desktop_file, encoding='utf-8')

                    if 'Desktop Entry' in parser:
                        entry = parser['Desktop Entry']
                        app_id = desktop_file.stem
                        categories_str = entry.get('Categories', '')

                        # Checagem mais robusta de 'Categories'
                        categories = set(categories_str.split(';'))
                        categories.discard('')

                        is_setting = (
                            'Settings' in categories
                            or 'big' in app_id.lower()
                        )

                        if (is_setting and
                                not entry.getboolean(
                                    'NoDisplay',
                                    fallback=False
                                ) and app_id not in found_ids):

                            # Função helper aninhada para DRY
                            def get_localized(_key: str) -> str:
                                if _lang and f"{_key}[{_lang}]" in entry:
                                    return entry[f"{_key}[{_lang}]"]
                                if _code and f"{_key}[{_code}]" in entry:
                                    return entry[f"{_key}[{_code}]"]
                                return entry.get(_key, "")

                            app_info: DesktopAppInfo = {
                                "name": get_localized("Name"),
                                "comment": get_localized("Comment"),
                                "icon": entry.get(
                                    'Icon',
                                    'application-x-executable'
                                ),
                                "exec": entry.get('Exec', ''),
                                "id": app_id
                            }

                            # Agrupamento por categoria XFCE
                            if 'X-XFCE-PersonalSettings' in categories:
                                grouped_apps["personal"].append(app_info)
                            elif 'X-XFCE-HardwareSettings' in categories:
                                grouped_apps["hardware"].append(app_info)
                            elif 'X-XFCE-SystemSettings' in categories:
                                grouped_apps["system"].append(app_info)
                            elif 'big' in app_id:
                                grouped_apps["big"].append(app_info)
                            else:
                                # 'Settings' mas sem categoria XFCE específica
                                grouped_apps["other"].append(app_info)

                            found_ids.add(app_id)

                except configparser.Error as e:
                    # Log silencioso de falha de parse, não quebra a execução
                    print(f"Erro ao analisar {desktop_file}: {e}")
                except Exception as e:
                    print(f"Erro inesperado processando {desktop_file}: {e}")

        # Ordena alfabeticamente cada lista para exibição na UI
        for category_list in grouped_apps.values():
            category_list.sort(key=lambda app: app['name'].lower())

        return grouped_apps
