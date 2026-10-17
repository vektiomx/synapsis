"""Store outcome-bearing experience with reproducible evidence, without claiming truth."""
import hashlib
from pathlib import Path

from memory_cycle import valid_text, project_path
from memory_store import MemoryStore, SECRET


def learn(project, folder, filename, experience, source):
    if isinstance(experience,dict) and 'when' in experience:
        from experience_engine import ExperienceStore
        return ExperienceStore(folder,project).save(filename,experience,source)
    root = Path(project_path(project))
    if not isinstance(experience, dict) or set(experience) - {'task','action','outcome','evidence','limitations'}:
        raise ValueError('Experiencia inválida.')
    for key in ('task', 'action', 'outcome'):
        valid_text(experience.get(key), 4000)
    evidence = experience.get('evidence')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
        raise ValueError('Incluye de 1 a 8 evidencias locales con path y sha256.')
    citations=[]
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'path','sha256'} or not isinstance(item.get('path'), str):
            raise ValueError('Evidencia inválida.')
        path=(root/item['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>2_000_000:
            raise ValueError('La evidencia debe ser un archivo del proyecto de hasta 2 MB.')
        from archivos import es_sensible
        if es_sensible(str(path)):
            raise ValueError('No uses archivos sensibles como evidencia.')
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item.get('sha256'):
            raise ValueError('La evidencia cambió; vuelve a verificar el resultado.')
        citations.append(str(path.relative_to(root))+' · sha256:'+actual)
    limits=experience.get('limitations', 'Resultado comunicado por el agente; la huella no certifica causalidad ni corrección.')
    valid_text(limits,2000)
    content='\n\n'.join(['## Tarea\n'+experience['task'], '## Acción\n'+experience['action'],
        '## Resultado observado\n'+experience['outcome'], '## Evidencia\n'+'\n'.join(citations), '## Límites\n'+limits])
    return MemoryStore(folder).save(filename=filename,name=filename,description=experience['task'][:500],kind='reference',
        content=content,index_line=f'- [{filename}]({filename}.md) — experiencia con resultado y evidencia',
        source=source,state='inferred',cues=[experience['task'][:80].replace('\n',' ')])
