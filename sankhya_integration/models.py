from django.db import models

# Modelos serão definidos conforme necessidade do projeto
from django.utils import timezone


class RastreioAudit(models.Model):
    """Audit log das atribuições e desvinculações de lote do módulo Rastreio.

    Cada registro representa UMA chamada bem-sucedida de
    api_rastreio_atribuir_lote ou api_rastreio_desvincular_lote.
    Permite responder "quem vinculou esse lote ao pedido X?" sem precisar
    de acesso aos logs do servidor.
    """
    ACAO_ATRIBUIR    = 'ATRIBUIR'
    ACAO_DESVINCULAR = 'DESVINCULAR'
    ACAO_CHOICES = [
        (ACAO_ATRIBUIR,    'Atribuir lote ao pedido'),
        (ACAO_DESVINCULAR, 'Desvincular lote do pedido'),
    ]

    acao         = models.CharField(max_length=16, choices=ACAO_CHOICES, db_index=True)
    nunota       = models.IntegerField(db_index=True)
    sequencia    = models.IntegerField()
    codagregacao = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    qtd          = models.DecimalField(max_digits=14, decimal_places=3, blank=True, null=True)
    codusu       = models.IntegerField(blank=True, null=True, db_index=True)
    nomeusu      = models.CharField(max_length=80, blank=True, null=True)
    detalhe      = models.JSONField(default=dict, blank=True)
    created_at   = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Audit Rastreio'
        verbose_name_plural = 'Auditoria do Rastreio'

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.acao} NUNOTA={self.nunota} SEQ={self.sequencia}"


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
