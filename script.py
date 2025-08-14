import os
import configparser
import subprocess
import shlex

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, ScrollablePane
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.application import get_app
from prompt_toolkit.shortcuts import message_dialog

# ---------- Helpers ----------

def clean_exec_cmd(exec_cmd):
    """Remove field codes like %U, %u, %F, %f, %i, %c, %k"""
    return [arg for arg in shlex.split(exec_cmd) if not arg.startswith("%")]

def list_apps():
    """Return list of launchable apps from .desktop files"""
    dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]
    apps = []
    for directory in dirs:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if filename.endswith(".desktop"):
                    filepath = os.path.join(directory, filename)
                    config = configparser.ConfigParser(interpolation=None)
                    try:
                        config.read(filepath)
                        entry = config.get("Desktop Entry", "Name", fallback=None)
                        exec_cmd = config.get("Desktop Entry", "Exec", fallback=None)
                        terminal = config.get("Desktop Entry", "Terminal", fallback="false").lower() == "true"
                        no_display = config.get("Desktop Entry", "NoDisplay", fallback="false").lower() == "true"

                        if entry and exec_cmd and not no_display:
                            apps.append((entry, exec_cmd))
                    except Exception:
                        continue
    return apps

def show_error(msg):
    """Display an error popup"""
    message_dialog(title="Error", text=msg).run()

# ---------- App Data ----------

apps = list_apps()
all_app_names = [a[0] for a in apps]
app_dict = {name: cmd for name, cmd in apps}
filtered_apps = all_app_names.copy()
focus_index = [0]

# ---------- Styles ----------

style = Style.from_dict({
    "frame.border": "#888888",
    "frame.label": "bold",
    "selected": "reverse bold",
})

# ---------- Key Bindings ----------

kb = KeyBindings()

# ---------- Search Box ----------

completer = FuzzyWordCompleter(all_app_names)
search_box = TextArea(
    height=1,
    prompt="Search: ",
    multiline=False,
    completer=completer,
    complete_while_typing=True,
)

def on_search_change(_buf):
    text = search_box.text.strip().lower()
    filtered_apps[:] = [a for a in all_app_names if text in a.lower()]
    set_focus(0)
    rebuild_rows()
    get_app().layout.focus(search_box)

search_box.buffer.on_text_changed += lambda _: on_search_change(search_box.buffer)

# ---------- Row Management ----------

def set_focus(idx):
    if filtered_apps:
        focus_index[0] = min(max(idx, 0), len(filtered_apps) - 1)

def build_rows():
    rows = []
    for i, name in enumerate(filtered_apps):
        def get_fragments(appname=name, idx=i):
            is_selected = idx == focus_index[0]
            prefix = "▸ " if is_selected else "  "
            style_frag = "class:selected" if is_selected else ""
            return [(style_frag, prefix + appname)]

        ctl = FormattedTextControl(get_fragments, focusable=False)
        win = Window(
            content=ctl,
            height=1,
            style=lambda idx=i: "class:selected" if idx == focus_index[0] else "",
            always_hide_cursor=True,
        )
        rows.append(win)

    if not rows:
        ctl = FormattedTextControl(lambda: [("", " No apps found")])
        rows.append(Window(content=ctl, height=1))
    return rows

def rebuild_rows():
    global rows
    rows = build_rows()
    hsplit.children = rows

rows = build_rows()
hsplit = HSplit(rows)
app_pane = ScrollablePane(hsplit)

# ---------- Key Bindings ----------

@kb.add("up")
def move_up(event):
    if filtered_apps:
        set_focus((focus_index[0] - 1) % len(filtered_apps))
        rebuild_rows()

@kb.add("down")
def move_down(event):
    if filtered_apps:
        set_focus((focus_index[0] + 1) % len(filtered_apps))
        rebuild_rows()

@kb.add("enter")
def launch(event):
    if filtered_apps:
        name = filtered_apps[focus_index[0]]
        cmd = app_dict.get(name)
        if cmd:
            try:
                # Launch in a new session so terminal stays clean
                subprocess.Popen(clean_exec_cmd(cmd), start_new_session=True)
            except Exception as e:
                show_error(f"Error launching {name}:\n{e}")
        # Reset search and list
        search_box.text = ""
        filtered_apps[:] = all_app_names
        set_focus(0)
        rebuild_rows()
        get_app().layout.focus(search_box)
        event.app.invalidate()  # force redraw


@kb.add("q")
@kb.add("c-c")
def exit_(event):
    event.app.exit()

# ---------- Root Container ----------

root_container = HSplit([
    Frame(search_box, style="class:frame", title="[ Up/Down/Enter: select q: quit ]"),
    Frame(app_pane, style="class:frame", title="Applications"),
])

layout = Layout(root_container, focused_element=search_box)

# ---------- Run App ----------

app = Application(
    layout=layout,
    key_bindings=kb,
    full_screen=True,
    style=style,
    mouse_support=False,
)

if __name__ == "__main__":
    app.run()