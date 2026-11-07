"use client";

import { CampoSelecao, CampoTexto } from "@/components/formularios/campos";
import type { Erros, Valores } from "@/lib/formularios";
import type { Referencias, TipoProcesso } from "@/lib/tipos";

/** Campos de dados de um processo, por tipo. Controlado: quem usa guarda os valores (criar ou editar). */
export function FormDados({
  tipo,
  valores,
  aoMudar,
  erros,
  referencias,
}: {
  tipo: TipoProcesso;
  valores: Valores;
  aoMudar: (campo: string, valor: string) => void;
  erros: Erros;
  referencias: Referencias;
}) {
  const opcoes = (lista: string[]) => lista.map((v) => [v, v] as [string, string]);
  const campo = (nome: string) => ({
    valor: valores[nome] ?? "",
    aoMudar: (v: string) => aoMudar(nome, v),
    erro: erros[nome],
  });
  const consulado = (
    <CampoSelecao
      rotulo="Consulado"
      opcoes={opcoes(referencias.consulados)}
      permiteVazio
      rotuloVazio="Ainda não definido"
      dica="Obrigatório quando houver data de CASV ou entrevista."
      {...campo("consulado")}
    />
  );

  if (tipo === "PASS")
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <CampoTexto rotulo="Data na Polícia Federal" tipo="date" {...campo("data_pf")} />
        <CampoTexto rotulo="Prazo" tipo="date" {...campo("prazo_pf")} />
        <CampoTexto rotulo="Observação" multilinha className="sm:col-span-2" {...campo("observacao")} />
      </div>
    );

  if (tipo === "REN")
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {consulado}
        <CampoTexto
          rotulo="CASV"
          tipo="date"
          dica="O despacho é calculado: 7 dias antes."
          {...campo("data_casv")}
        />
        <CampoSelecao rotulo="Documentos" opcoes={opcoes(referencias.docs_ren)} {...campo("docs")} />
        <CampoSelecao rotulo="Rascunho" opcoes={opcoes(referencias.rascunho)} {...campo("status_rascunho")} />
        <CampoTexto rotulo="Endereço" className="sm:col-span-2" {...campo("endereco")} />
        <CampoTexto rotulo="Código de rastreio" {...campo("codigo_rastreio")} />
        <CampoTexto rotulo="Observação" multilinha className="sm:col-span-2" {...campo("observacao")} />
      </div>
    );

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {consulado}
      <CampoSelecao
        rotulo="Monitoramento"
        opcoes={opcoes(referencias.monitoramento)}
        {...campo("monitoramento")}
      />
      <CampoTexto rotulo="CASV" tipo="date" {...campo("data_casv")} />
      <CampoTexto rotulo="Entrevista" tipo="date" {...campo("data_entrevista")} />
      <CampoTexto rotulo="Vencimento da taxa" tipo="date" {...campo("data_vencimento_taxa")} />
      <CampoSelecao rotulo="Rascunho" opcoes={opcoes(referencias.rascunho)} {...campo("status_rascunho")} />
      <CampoSelecao rotulo="Orientação" opcoes={opcoes(referencias.orientacao)} {...campo("orientacao")} />
      <CampoTexto rotulo="Data da orientação" tipo="date" {...campo("orientacao_data")} />
      <CampoSelecao
        rotulo="Orientado por"
        opcoes={referencias.usuarios.map((u) => [String(u.id), u.nome])}
        permiteVazio
        rotuloVazio="Ninguém indicado"
        {...campo("orientacao_por_id")}
      />
      <CampoTexto rotulo="Código de rastreio" {...campo("codigo_rastreio")} />
      <CampoTexto rotulo="Observação" multilinha className="sm:col-span-2" {...campo("observacao")} />
    </div>
  );
}
