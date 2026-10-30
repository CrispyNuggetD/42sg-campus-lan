"""Parse host-resolved presence selectors, separate from counts and academic filters."""

from .intake_selectors import cluster_selector
from .seat_selectors import parse_seat_selection

def parse_presence(bits):
    words=[b.lower() for b in bits]
    sources=[b for b in words if b in ('online','verified')]
    if not sources:
        if any(cluster_selector(word) or word=='cluster' for word in words):sources=['online']
        else:return None
    usage='Use /sabo c1r3:4s1:2 [COUNT], /sabo c1:2, /sabo online [COUNT] [cluster 1|2], or /sabo verified [COUNT].'
    if len(sources)!=1:raise ValueError(usage)
    source=sources[0];requested=None;cluster=None;i=0
    while i<len(words):
        word=words[i];i+=1
        if word==source:continue
        if word=='cluster':
            if i>=len(words):raise ValueError(usage)
            location=parse_seat_selection('c'+words[i]);i+=1
        elif cluster_selector(word):
            location=parse_seat_selection(word)
        elif word.isdecimal():
            if requested is not None:raise ValueError(usage)
            requested=int(word)
            if not 1<=requested<=50:raise ValueError('Choose a count from 1 to 50.')
            continue
        else:raise ValueError(usage)
        if source!='online' or cluster is not None:raise ValueError('Choose one cluster for /sabo online; verified is a sign-in selector, not campus presence.')
        cluster=location
    return source,requested,cluster
