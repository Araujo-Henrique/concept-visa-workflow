"use client";

import { Pencil } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { editarProcesso } from "@/app/acoes/processos";
import { FormDados } from "@/components/processos/form-dados";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { corpoEdicao, validarProcesso, valoresDoProcesso, type Erros, type Valores } from "@/lib/formularios";
import type { ProcessoDetalhe, Referencias, TipoProcesso } from "@/lib/tipos";

/** Painel lateral para editar os dados do processo. Só o que mudou vai para a API. */
export function EditarDados({
  tipo,
  detalhe,
  referencias,
}: {
  tipo: TipoProcesso;
  detalhe: ProcessoDetalhe;
  referencias: Referencias;
}) {
  const [aberto, setAberto] = useState(false);
  const [antes, setAntes] = useState<Valores>({});
  const [valores, setValores] = useState<Valores>({});
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();

  const abrir = () => {
    const atuais = valoresDoProcesso(tipo, detalhe);
    setAntes(atuais);
    setValores(atuais);
    setErros({});
    setErroGeral(null);
    setAberto(true);
  };

  const salvar = () => {
    const mudancas = corpoEdicao(tipo, antes, valores);
    if (Object.keys(mudancas).length === 0) {
      setAberto(false);
      return;
    }
    // como na API: a regra do consulado só vale se a edição mexe nele ou nas datas (histórico "N/D")
    const encontrados = validarProcesso(tipo, valores, new Set(Object.keys(mudancas)));
    setErros(encontrados);
    if (Object.keys(encontrados).length) return;
    iniciar(async () => {
      const r = await editarProcesso(tipo, detalhe.id, mudancas);
      if (r.ok) {
        toast.success("Dados atualizados");
        setAberto(false);
      } else setErroGeral(r.erro);
    });
  };

  return (
    <>
      <Button variant="outline" size="sm" onClick={abrir}>
        <Pencil className="size-3.5" /> Editar dados
      </Button>
      <Sheet open={aberto} onOpenChange={setAberto}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>Editar dados do processo #{detalhe.id}</SheetTitle>
            <SheetDescription>A situação muda pela rota do processo, não por aqui.</SheetDescription>
          </SheetHeader>
          <form
            className="px-4 pb-6"
            onSubmit={(e) => {
              e.preventDefault();
              salvar();
            }}
            noValidate
          >
            <FormDados
              tipo={tipo}
              valores={valores}
              erros={erros}
              referencias={referencias}
              aoMudar={(campo, valor) => setValores((v) => ({ ...v, [campo]: valor }))}
            />
            {erroGeral && (
              <p role="alert" className="mt-4 rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
                {erroGeral}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setAberto(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={salvando}>
                {salvando ? "Salvando…" : "Salvar"}
              </Button>
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </>
  );
}
