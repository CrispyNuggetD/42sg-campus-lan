"""Explicit bulk setup of popup categories; action approvals remain separate."""
from .popup_permissions import CATEGORIES

LABELS={
    'search':'Open web searches with the selected engine',
    'browser':'General browser pages (fallback for the categories below)',
    'help':'Open the help guide in your browser',
    'forknite':'Open FORKNITE game pages',
    'profiles':'Open Intra profile pages',
    'signin':'Open 42 sign-in pages',
    'tools':'Open browser tool panels',
    'photos':'Open photo pages and approved photo-save tools',
    'notifications':'Show desktop notifications',
    'terminals':'Open game, cluster and tool terminals',
}

class PermissionSetup:
    def permission_setup_command(self,text):
        parts=text.split()
        if not parts or parts[0] not in ('/setup','/allow'):return False
        if len(parts)>2 or (len(parts)==2 and parts[1] not in ('all','batch')):
            self.lines.append('Use /setup, /allow batch, or /allow all.');return True
        mode=parts[1] if len(parts)==2 else 'batch'
        prompts=self.popup_prompts()
        if getattr(self,'permission_prompt',False):
            self.permission_setup_draft=getattr(self,'permission_saved_input','')
            self.permission_prompt=False
        else:self.permission_setup_draft=''
        if prompts.active:
            # Re-evaluate popup policy after setup; decision/session approvals stay pending.
            prompts.pending.appendleft(prompts.active);prompts.active=None
        self.wizard=('permissions-'+mode,list(CATEGORIES));self.play=False
        self.lines.extend(['POPUP PERMISSION SETUP — saved on your account/device',
                           'Categories: '+', '.join(CATEGORIES),
                           'These permissions do not approve file receipts, group joins, broadcasts, sound or system-volume changes.'])
        self.permission_setup_question()
        return True

    def permission_setup_question(self):
        mode,remaining=self.wizard
        if mode=='permissions-all':
            self.lines.append('Allow ALL listed popup categories permanently? [y/N] /cancel exits.')
        else:
            category=remaining[0]
            self.lines.append(category+': '+LABELS[category]+' — [y/N], all = allow entire list, /cancel exits.')
            if category=='browser':self.lines.append('For the general browser fallback, No keeps asking; specific browser categories are chosen next.')

    def permission_setup_answer(self,text):
        mode,remaining=self.wizard;answer=text.strip().lower()
        permissions=self.popup_prompts().permissions
        def finish(message):
            self.wizard=None;self.input=getattr(self,'permission_setup_draft','')
            self.lines.append(message+' Change later: /settings permissions CATEGORY ask|allow|deny.')
        try:
            if answer=='/cancel':finish('Permission setup cancelled; choices already saved remain.');return
            if answer=='all' or (mode=='permissions-all' and answer in ('y','yes')):
                permissions.set('all','allow');finish('All popup categories allowed.');return
            if mode=='permissions-all' and answer in ('','n','no'):
                finish('All-category permission request declined.');return
            if answer not in ('','y','yes','n','no'):
                self.lines.append('Answer y, n, all or /cancel.');return
            category=remaining.pop(0)
            policy='allow' if answer in ('y','yes') else 'ask' if category=='browser' else 'deny'
            permissions.set(category,policy)
            self.lines.append(category+': '+policy)
            if not remaining:finish('Permission setup complete.');return
            self.permission_setup_question()
        except (OSError,ValueError) as error:
            finish('Could not save permission setup: '+str(error))
