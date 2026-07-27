from django.contrib import admin
from aplicator.models import TeamMember, CompanyContextBlock, Accelerator, Question, CanonicalAnswer, GeneratedAnswer

admin.site.register(TeamMember)
admin.site.register(CompanyContextBlock)
admin.site.register(Accelerator)
admin.site.register(Question)
admin.site.register(CanonicalAnswer)
admin.site.register(GeneratedAnswer)
