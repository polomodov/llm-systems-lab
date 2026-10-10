"""Select the exact artifact, never by manifest ordering."""
def select_artifact(manifest, *, format, repository, revision):
    matches=[a for a in manifest['artifacts'] if a['format']==format and a['repository']==repository and a['revision']==revision]
    if len(matches)!=1:
        raise ValueError('Expected exactly one artifact matching format/repository/revision')
    return matches[0]

def missing_artifact_pins(artifact, pins):
    by_path={p['path']:p for p in pins['files']}
    missing=[]
    for file in artifact['files']:
        path=file['local_path']
        actual=by_path.get(path)
        if not actual or actual['bytes']!=file['bytes'] or actual['sha256']!=file['sha256']:
            missing.append(path)
    return missing
