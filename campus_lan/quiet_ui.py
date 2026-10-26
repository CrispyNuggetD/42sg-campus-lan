"""Keyboard requests and pinned-host schedule data; no executable remote actions."""
import time
from . import audio_quiet


class QuietUI:
    def quiet_update(self,data):
        state=data.get('quiet')
        if state is None:return
        try:
            from .auth_client import load_trust,fingerprint
            if audio_quiet.accept(state,fingerprint(load_trust())):
                now=time.time();old=[w for w in getattr(self,'quiet_queue',[]) if w['end']>now]
                current=[w for w in state['windows'] if w['end']>now]
                key=lambda rows:{(w['start'],w['end'],w['reason']) for w in rows}
                if key(current)-key(old):self.lines.append('Exam/app-audio mute queue updated by the trusted host (calendar settings, not a software or security update). /exams shows visible dates.')
                self.quiet_queue=current
        except (OSError,ValueError):pass

    def quiet_tick(self):
        now=time.time()
        if now<getattr(self,'quiet_next',0):return
        self.quiet_next=now+15
        self.quiet_queue=[w for w in getattr(self,'quiet_queue',[]) if w['end']>now]
        if not getattr(self,'quiet_notices',None):self.quiet_notices=audio_quiet.QuietNotices()
        from .koel_sound import SoundChoice
        audible=SoundChoice(self.name).read()['enabled']
        self.lines.extend(self.quiet_notices.tick(audio_quiet.schedule(),now,audible))

    def quiet_command(self,text):
        parts=text.split()
        if parts[:1]==['/exams']:
            if len(parts)!=1:self.lines.append('Use /exams for the shared host calendar cache.');return True
            from .announcement_client import act
            self.announcement_work(lambda:dict(exam_schedule=act('exams')))
            return True
        if not parts or parts[0]!='/quiet':return False
        try:
            if len(parts)==1 or parts[1:]==['status']:
                self.lines.append('LAN42 app audio: '+('quiet' if audio_quiet.active() else 'normal opt-in sound preferences')+'. Precautionary SGT defaults: Wednesday 15–18, every Saturday 13–16. System output is untouched.')
                self.lines.append('/exams — cached visible SG exams | admin: /quiet MINUTES (1–720) | /quiet off clears only the manual window.')
            elif len(parts)==2:
                minutes=0 if parts[1]=='off' else int(parts[1])
                if not 0<=minutes<=720:raise ValueError('Use 1–720 minutes, or off.')
                from .announcement_client import act
                self.popup_prompts().confirm('Set a '+str(minutes)+'-minute LAN42-only audio quiet window through the trusted host? Only configured admins are accepted. Clearing manual quiet never enables sound or cancels the built-in exam defaults.',
                    lambda:self.announcement_work(lambda:dict(quiet_result=act('quiet',minutes=minutes))))
            else:raise ValueError('Use /quiet status, /quiet MINUTES or /quiet off.')
        except (OSError,ValueError) as error:self.lines.append(str(error))
        return True
