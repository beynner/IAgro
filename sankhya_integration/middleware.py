import time
from django.utils.deprecation import MiddlewareMixin

class ControleInatividadeMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 1. Se o usuário não está logado (não tem 'codusu'), deixa passar reto
        if 'codusu' not in request.session:
            return

        tempo_atual = time.time()
        ultima_atividade = request.session.get('ultima_atividade')
        
        # 3600 segundos = 60 minutos
        limite_segundos = 3600 

        if ultima_atividade:
            tempo_ocioso = tempo_atual - ultima_atividade
            
            if tempo_ocioso > limite_segundos:
                # 2. O TEMPO ESTOUROU! Destrói a sessão completamente no servidor
                request.session.flush()
                # O Django vai seguir o fluxo, e o seu @exige_grupo vai barrar o usuário
                return

        # 1. Atualiza o timestamp interno
        request.session['ultima_atividade'] = tempo_atual
        # 2. Força o Django a reenviar o Cookie com +60 minutos de vida
        request.session.set_expiry(limite_segundos)