import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Simulation

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Simulation)
def audit_simulation_save(sender, instance, created, **kwargs):
    acao = 'CRIADA' if created else 'ATUALIZADA'
    logger.info(
        "Simulação %s | ID=%s | lote=%s | total=%s | por=%s",
        acao, instance.id, instance.lote, instance.total, instance.created_by,
    )


@receiver(post_delete, sender=Simulation)
def audit_simulation_delete(sender, instance, **kwargs):
    logger.info(
        "Simulação EXCLUÍDA | ID=%s | lote=%s | por=%s",
        instance.id, instance.lote, instance.created_by,
    )
