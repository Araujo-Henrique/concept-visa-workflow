"use client";

import { useState } from "react";

import { EditarDados } from "@/components/passaporte/editar-dados";
import { PaginaPessoas } from "@/components/passaporte/pagina-pessoas";
import { PaginaDados, PaginaHistorico } from "@/components/passaporte/paginas";
import { direcaoEntre, Passaporte, type IdPagina } from "@/components/passaporte/passaporte";
import { RotaSituacao } from "@/components/passaporte/rota-situacao";
import type { Evento, LinhaPainel, ProcessoDetalhe, Referencias } from "@/lib/tipos";

/** Detalhe do processo: o passaporte (esquerda) e a rota de situações (direita), conversando entre si. */
export function VistaProcesso({
  linha,
  detalhe,
  eventos,
  referencias,
  permissoes,
}: {
  linha: LinhaPainel;
  detalhe: ProcessoDetalhe;
  eventos: Evento[];
  referencias: Referencias;
  permissoes: { escrever: boolean; apagar: boolean };
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
          dados: (
            <PaginaDados
              linha={linha}
              detalhe={{ ...detalhe, situacao: linha.situacao }}
              acao={
                permissoes.escrever && (
                  <EditarDados tipo={linha.tipo} detalhe={detalhe} referencias={referencias} />
                )
              }
            />
          ),
          pessoas: (
            <PaginaPessoas
              processoId={linha.processo_id}
              solicitantes={detalhe.solicitantes}
              comDs160={linha.tipo !== "PASS"}
              statusDs={referencias.status_ds}
              permissoes={permissoes}
            />
          ),
          historico: <PaginaHistorico eventos={eventos} novo={novoCarimbo} />,
        }}
      />
      <RotaSituacao
        processoId={linha.processo_id}
        atual={linha.situacao}
        situacoes={referencias.situacoes[linha.tipo]}
        visitadas={visitadas}
        podeMudar={permissoes.escrever}
        aoCarimbar={(id) => {
          setNovoCarimbo(id); // o carimbo novo "bate" na página
          irPara("historico");
        }}
      />
    </div>
  );
}
