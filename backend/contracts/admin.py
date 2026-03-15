# backend/contracts/admin.py
from django.contrib import admin
from .models import Contract, Obligation, ContractObligation

admin.site.register(Contract)
admin.site.register(Obligation)
admin.site.register(ContractObligation)



