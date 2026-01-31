__all__ = ['IR', 'SKC', 'SKC_HM', 'SKE', 'SKE_XREF', 'SKE_IRI', 'SKE_HR', 'SKE_MO', 'SKI', 'SKI_HP', 'SKF', 'N', 'NIA', 'SKC_HN',
           'SKE_HN', 'SKI_HN', 'SKF_HN', 'N_HN']

from .schema_sqla import *
from sqlalchemy.orm import aliased

# Using Aliases like this massively simplifies the use of SQLAlchemy
IR = aliased(InformationResource)

SKC = aliased(ScientificKnowledgeCollection)
SKC_HM = aliased(ScientificKnowledgeCollectionHasMembers)
SKE = aliased(ScientificKnowledgeExpression)
SKE_XREF = aliased(ScientificKnowledgeExpressionXref)
SKE_IRI = aliased(ScientificKnowledgeExpressionIri)
SKE_HR = aliased(ScientificKnowledgeExpressionHasRepresentation)
SKE_MO = aliased(ScientificKnowledgeExpressionMemberOf)
SKI = aliased(ScientificKnowledgeItem)
SKI_HP = aliased(ScientificKnowledgeItemHasPart)
SKF = aliased(ScientificKnowledgeFragment)

N = aliased(Note)
NIA = aliased(NoteIsAbout)
SKC_HN = aliased(ScientificKnowledgeCollectionHasNotes)
SKE_HN = aliased(ScientificKnowledgeExpressionHasNotes)
SKI_HN = aliased(ScientificKnowledgeItemHasNotes)
SKF_HN = aliased(ScientificKnowledgeFragmentHasNotes)
N_HN = aliased(NoteHasNotes)

