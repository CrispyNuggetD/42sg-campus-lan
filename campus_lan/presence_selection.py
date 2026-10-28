"""Parse host-resolved presence selectors, separate from counts and academic filters."""


def parse_presence(bits):
    words=[b.lower() for b in bits]
    sources=[b for b in words if b in ('online','verified')]
    if not sources:return None
    usage='Use /sabo online [COUNT] [cluster 1|2] or /sabo verified [COUNT].'
    if len(sources)!=1:raise ValueError(usage)
    source=sources[0];requested=None;cluster=None;i=0
    while i<len(words):
        word=words[i];i+=1
        if word==source:continue
        if word=='cluster':
            if i>=len(words) or words[i] not in ('1','2'):raise ValueError(usage)
            location=int(words[i]);i+=1
        elif word in ('c1','c2','cluster1','cluster2'):location=int(word[-1])
        elif word.isdecimal():
            if requested is not None:raise ValueError(usage)
            requested=int(word)
            if not 1<=requested<=50:raise ValueError('Choose a count from 1 to 50.')
            continue
        else:raise ValueError(usage)
        if source!='online' or cluster is not None:raise ValueError('Choose one cluster for /sabo online; verified is a sign-in selector, not campus presence.')
        cluster=location
    return source,requested,cluster
