from django.db import models

# Modelos serão definidos conforme necessidade do projeto
from django.utils import timezone

class Simulation(models.Model):
		"""Armazena simulações comerciais geradas no painel.

		Payload guarda os dados da simulação (JSON), por exemplo:
		{
			"lote": "26086",
			"prod": "TOMATE ITALIANO",
			"price_cx": 60.0,
			"q_cx": 116,
			"q_kg": 2676,
			"obs_adm": "...",
			"obs_prod": "..."
		}
		"""
		name = models.CharField(max_length=160, blank=True, null=True)
		lote = models.CharField(max_length=64, blank=True, null=True, db_index=True)
		payload = models.JSONField(default=dict)
		total = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
		created_by = models.CharField(max_length=80, blank=True, null=True)
		created_at = models.DateTimeField(default=timezone.now)
		updated_at = models.DateTimeField(auto_now=True)

		class Meta:
				ordering = ("-created_at",)
				verbose_name = "Simulação Comercial"
				verbose_name_plural = "Simulações Comerciais"

		def __str__(self) -> str:
				return f"Simulação {self.id} - {self.lote or self.name or '—'}"
