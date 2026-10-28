"""Shared campus cluster command aliases (no API access)."""


def normalize_cluster_command(text):
    command, _, argument = text.strip().partition(' ')
    argument = argument.strip()
    if command in ('./clusters', '/cluster'):
        command = '/clusters'
    elif command in ('/cluster1', '/c1', '/cluster2', '/c2'):
        if not argument:
            argument = command[-1]
        else:
            argument = 'invalid'
        command = '/clusters'
    return command + (' ' + argument if argument else '')
