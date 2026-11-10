"""One small, nonmodal desktop preview of already cached cluster photos."""
import io
import json
from pathlib import Path
import subprocess
import sys
import threading

from .avatar_cache import AvatarCache


class PhotoPreview:
    def __init__(self, report):
        self.report = report
        self.process = None

    def show(self, login):
        # No profile lookup, browser, photo acquisition or network fallback.
        try:
            AvatarCache().read(login)
        except (OSError, ValueError):
            self.close()
            self.report('No existing local photo for ' + login + '.')
            return
        try:
            if self.process is None or self.process.poll() is not None:
                self.process = subprocess.Popen(
                    [sys.executable, '-m', 'campus_lan.cluster_photo'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, bufsize=1,
                    cwd=str(Path(__file__).resolve().parent.parent))
                process = self.process
                def notices():
                    for line in process.stdout:
                        self.report(line.strip()[:180])
                threading.Thread(target=notices, daemon=True).start()
            self.process.stdin.write(json.dumps(login) + '\n')
            self.process.stdin.flush()
        except (OSError, ValueError):
            self.close()
            self.report('Local photo preview unavailable; try selecting the student again.')

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.stdin:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def photo_caption(login):
    from .student_names import cached_name
    name = cached_name(login)
    return (name + '\n' if name else '') + login + ' · local photo · Esc closes'


def copy_fields(login, name):
    details = ((name + '\n') if name else '') + login
    details += '\nhttps://profile-v3.intra.42.fr/users/' + login
    return dict(name=name, intra=login, details=details)


def present(root):
    """Keep the small preview visible while clicks remain in the terminal."""
    root.attributes('-topmost', True)
    root.deiconify()
    root.lift()


def main():
    try:
        import queue
        import tkinter as tk
        from PIL import Image, ImageTk
        root = tk.Tk()
        root.withdraw()
        root.title('LAN42 · cached photo')
        root.resizable(False, False)
        root.geometry('280x320+%d+40' % max(0, root.winfo_screenwidth()-300))
        # Keep keyboard focus in the terminal; only the small preview floats.
        label = tk.Label(root)
        label.pack(expand=True)
        details = tk.Frame(root)
        details.pack(fill='x', padx=8, pady=4)
        caption = tk.Text(details, height=3, width=1, wrap='word',
                          font='TkDefaultFont', relief='flat', cursor='xterm',
                          state='disabled', exportselection=False)
        caption.pack(fill='x')
        copy_values = {}
        copy_labels = dict(name='Copy name', intra='Copy Intra', details='Copy details')
        actions = tk.Frame(details)
        actions.pack(fill='x', pady=(2, 0))
        buttons = {}
        def copy(field):
            value = copy_values.get(field)
            if value:
                root.clipboard_clear()
                root.clipboard_append(value)
                for key, button in buttons.items():
                    button.configure(text=copy_labels[key])
                buttons[field].configure(text='Copied')
        for column, field in enumerate(copy_labels):
            button = tk.Button(actions, text=copy_labels[field], padx=3,
                               command=lambda field=field: copy(field))
            button.grid(row=0, column=column, sticky='ew')
            actions.columnconfigure(column, weight=1)
            buttons[field] = button
        root.bind('<Escape>', lambda event: root.withdraw())
        root.protocol('WM_DELETE_WINDOW', root.withdraw)
        incoming = queue.Queue()
        def read():
            for line in sys.stdin:
                incoming.put(json.loads(line))
            incoming.put(None)
        threading.Thread(target=read, daemon=True).start()
        def update():
            try:
                while True:
                    login = incoming.get_nowait()
                    if login is None:
                        root.destroy()
                        return
                    try:
                        data, _ = AvatarCache().read(login)
                        from .student_names import cached_name
                        name = cached_name(login)
                        copy_values.clear()
                        copy_values.update(copy_fields(login, name))
                        for field, button in buttons.items():
                            button.configure(text=copy_labels[field],
                                             state='disabled' if field=='name' and not name else 'normal')
                        caption.configure(state='normal')
                        caption.delete('1.0', 'end')
                        caption.insert('1.0', photo_caption(login))
                        caption.configure(state='disabled')
                        root.update_idletasks()
                        lines = caption.count('1.0', 'end-1c', 'displaylines')
                        caption.configure(height=max(2, (lines[0] if lines else 0)+1))
                        root.update_idletasks()
                        photo_height = max(80, min(256, 320-details.winfo_reqheight()-16))
                        with Image.open(io.BytesIO(data)) as image:
                            if image.width * image.height > 16_000_000:
                                raise ValueError('Image too large')
                            image.thumbnail((248, photo_height))
                            photo = ImageTk.PhotoImage(image.convert('RGB'))
                        label.configure(image=photo)
                        label.image = photo
                        present(root)
                    except (OSError, ValueError):
                        root.withdraw()
                        print('Existing local photo could not be displayed for ' + login + '.', flush=True)
            except queue.Empty:
                pass
            root.after(100, update)
        update()
        root.mainloop()
    except Exception:
        print('Photo preview needs a desktop session, Tk and Pillow on this computer.', flush=True)


if __name__ == '__main__':
    main()
