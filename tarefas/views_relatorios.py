"""Tela Relatórios: semanas salvas + semana atual (parcial), ver e baixar PDF."""

from datetime import date, datetime

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from . import relatorios
from .models import RelatorioSemanal
from .pdf import ErroPDF, html_para_pdf

# Ordem do bloco "Em aberto": atrasadas primeiro, depois aguardando, em andamento, a fazer.
ORDEM_ABERTAS = {"aguardando": 1, "em_andamento": 2, "a_fazer": 3}


def _semana_atual():
    return relatorios.semana_de(timezone.localdate())


def _dados_da_semana(inicio):
    """Semana atual: calculada na hora (parcial, não salva). Outras: a foto salva."""
    if inicio == _semana_atual():
        return relatorios.gerar_foto(inicio)
    relatorio = RelatorioSemanal.objects.filter(semana_inicio=inicio).first()
    if relatorio is None:
        raise Http404("Relatório não encontrado.")
    return relatorio.dados


def _data(texto):
    return date.fromisoformat(texto) if texto else None


def _momento(texto):
    return timezone.localtime(datetime.fromisoformat(texto)) if texto else None


def contexto_documento(inicio, recorte, incluir_obs):
    dados = _dados_da_semana(inicio)
    tarefas, reunioes, rotulo = relatorios.aplicar_recorte(dados, recorte)

    linhas = []
    for t in tarefas:
        linha = dict(t, prazo=_data(t["prazo"]), concluida_em=_momento(t["concluida_em"]))
        if not incluir_obs:
            linha["observacoes"] = ""  # observações só entram se marcar (são anotações pessoais)
        linhas.append(linha)
    reunioes = [dict(r, inicio=_momento(r["inicio"]), fim=_momento(r["fim"]),
                     observacoes=r["observacoes"] if incluir_obs else "") for r in reunioes]

    concluidas = sorted((t for t in linhas if t["concluida_na_semana"]), key=lambda t: t["concluida_em"])
    abertas = sorted(
        (t for t in linhas if t["aberta"]),
        key=lambda t: (not t["atrasada"], ORDEM_ABERTAS.get(t["status"], 9), t["prazo"] or date.max),
    )
    return {
        "inicio": _data(dados["inicio"]),
        "fim": _data(dados["fim"]),
        "parcial": dados["parcial"],
        "gerado_em": _momento(dados["gerado_em"]),
        "recorte_rotulo": rotulo,
        "concluidas": concluidas,
        "abertas": abertas,
        "reunioes": reunioes,
        "resumo": {
            "concluidas": len(concluidas),
            "novas": sum(1 for t in linhas if t["criada_na_semana"]),
            "abertas": len(abertas),
            "atrasadas": sum(1 for t in abertas if t["atrasada"]),
            "reunioes": len(reunioes),
        },
        "incluir_obs": incluir_obs,
        "fonte_url": (settings.BASE_DIR / "static" / "fonts" / "InterVariable.woff2").as_uri(),
    }


def _parametros(request, inicio_iso):
    try:
        inicio = date.fromisoformat(inicio_iso)
    except ValueError:
        raise Http404("Semana inválida.") from None
    return relatorios.semana_de(inicio), request.GET.get("recorte", "geral"), request.GET.get("obs") == "1"


def lista(request):
    relatorios.garantir_relatorios()  # gera semanas que terminaram e ainda não têm foto
    atual = _semana_atual()
    semanas = [{"inicio": atual, "parcial": True, "recortes": relatorios.recortes_de(relatorios.gerar_foto(atual))}]
    for r in RelatorioSemanal.objects.all():
        semanas.append({"inicio": r.semana_inicio, "parcial": False, "gerado_em": r.gerado_em,
                        "recortes": relatorios.recortes_de(r.dados)})
    return render(request, "tarefas/relatorios.html", {"semanas": semanas})


def ver(request, inicio):
    """O relatório no navegador (mesmo conteúdo do PDF)."""
    semana, recorte, obs = _parametros(request, inicio)
    return render(request, "tarefas/relatorio_documento.html", contexto_documento(semana, recorte, obs))


def baixar_pdf(request, inicio):
    semana, recorte, obs = _parametros(request, inicio)
    contexto = contexto_documento(semana, recorte, obs)
    html = render_to_string("tarefas/relatorio_documento.html", contexto, request)
    try:
        pdf = html_para_pdf(html)
    except ErroPDF as erro:
        return HttpResponse(f"Não foi possível gerar o PDF: {erro}", status=500, content_type="text/plain; charset=utf-8")
    sufixo = recorte.split(":", 1)[-1].replace(" ", "-").lower() if recorte != "geral" else "geral"
    nome = f"kairos-semana-{semana:%Y-%m-%d}-{sufixo}{'-parcial' if contexto['parcial'] else ''}.pdf"
    resposta = HttpResponse(pdf, content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
