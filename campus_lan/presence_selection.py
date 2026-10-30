"""Parse host-resolved presence selectors, separate from counts and academic filters."""

import re
from .intake_selectors import cluster_selector

def parse_presence(bits):
    words=[b.lower() for b in bits]
    sources=[b for b in words if b in ('online','verified')]
    if not sources:
        if any(cluster_selector(word) or word=='cluster' for word in words):sources=['online']
        else:return None
    usage='Use /sabo c1|c2 [COUNT], /sabo online [COUNT] [cluster 1|2], or /sabo verified [COUNT].'
    if len(sources)!=1:raise ValueError(usage)
    source=sources[0];requested=None;cluster=None;i=0
    while i<len(words):
        word=words[i];i+=1
        if word==source:continue
        if word=='cluster':
            if i>=len(words) or words[i] not in ('1','2'):raise ValueError(usage)
            location=int(words[i]);i+=1
        elif cluster_selector(word):
            location=int(re.search(r'\d+$',word).group())
            if location not in (1,2):raise ValueError('Only clusters C1 and C2 are supported; use I4 or intake4 for intake 4.')
        elif word.isdecimal():
            if requested is not None:raise ValueError(usage)
            requested=int(word)
            if not 1<=requested<=50:raise ValueError('Choose a count from 1 to 50.')
            continue
        else:raise ValueError(usage)
        if source!='online' or cluster is not None:raise ValueError('Choose one cluster for /sabo online; verified is a sign-in selector, not campus presence.')
        cluster=location
    return source,requested,cluster
