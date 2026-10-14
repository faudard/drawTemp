"""Shared access to the real Studio Fichier menu in Tk GUI smoke tests.

The editor moved rare file operations into a menu. Tests must activate the
public UI action instead of depending on a removed header button.
"""


def save_as(root):
    """Invoke Fichier -> Enregistrer sous… through the visible menu."""
    from tkinter import ttk

    def descendants(parent):
        for child in parent.winfo_children():
            yield child
            yield from descendants(child)

    file_button = next(
        (widget for widget in descendants(root)
         if isinstance(widget, ttk.Menubutton)
         and widget.cget('text').startswith('Fichier')),
        None,
    )
    if file_button is None:
        raise AssertionError('Le menu Fichier est introuvable.')
    menu = root.nametowidget(file_button.cget('menu'))
    menu.invoke('Enregistrer sous…')
