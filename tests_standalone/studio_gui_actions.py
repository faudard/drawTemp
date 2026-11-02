"""Helpers for exercising the real DrawTemp Studio native File menu."""


def menu_named(root, name):
    """Return a native Tk submenu by its visible top-level label."""
    bar_name = root.cget('menu')
    if not bar_name:
        raise AssertionError('The native Studio menubar is missing.')
    bar = root.nametowidget(bar_name)
    for index in range(bar.index('end') + 1):
        if bar.entrycget(index, 'label') == name:
            return root.nametowidget(bar.entrycget(index, 'menu'))
    raise AssertionError(f'Studio menu {name!r} is missing.')


def save_as(root):
    """Invoke File -> Save Content As… through the native menubar."""
    menu_named(root, 'File').invoke('Save Content As…')
