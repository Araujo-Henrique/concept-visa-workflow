"use client";

import { useState } from "react";

import { PaginaDados, PaginaHistorico, PaginaPessoas } from "@/components/passaporte/paginas";
import { direcaoEntre, Passaporte, type IdPagina } from "@/components/passaporte/passaporte";
import { RotaSituacao } from "@/components/passaporte/rota-situacao";
import type { Evento, LinhaPainel, ProcessoDetalhe } from "@/lib/tipos";

/** Detalhe do processo: o passaporte (esquerda) e a rota de situações (direita), conversando entre si. */
export function VistaProcesso({
  linha,
  detalhe,
  eventos,
  situacoes,
  podeEscrever,
}: {
  linha: LinhaPainel;
  detalhe: ProcessoDetalhe;
  eventos: Evento[];
  situacoes: string[];
  podeEscrever: boolean;
}) {
  const [pagina, setPagina] = useState<IdPagina>("dados");
  const [direcao, setDirecao] = useState(1);
  const [novoCarimbo, setNovoCarimbo] = useState<number | null>(null);

  const irPara = (para: IdPagina) => {
    setDirecao(direcaoEntre(pagina, para));
    setPagina(para);
  };

  const visitadas = new Set(eventos.map((e) => e.situacao_nova).filter((s): s is string => Boolean(s)));

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <Passaporte
        linha={linha}
        pagina={pagina}
        direcao={direcao}
        aoMudar={irPara}
        paginas={{
          dados: <PaginaDados linha={linha} detalhe={{ ...detalhe, situacao: linha.situacao }} />,
          pessoas: (
            <PaginaPessoas
              solicitantes={detalhe.solicitantes}
              podeEscrever={podeEscrever}
              comDs160={linha.tipo !== "PASS"}
            />
          ),
          historico: <PaginaHistorico eventos={eventos} novo={novoCarimbo} />,
        }}
      />
      <RotaSituacao
        processoId={linha.processo_id}
        atual={linha.situacao}
        situacoes={situacoes}
        visitadas={visitadas}
        podeMudar={podeEscrever}
        aoCarimbar={(id) => {
          setNovoCarimbo(id); // o carimbo novo "bate" na página
          irPara("historico");
        }}
      />
    </div>
  );
}
