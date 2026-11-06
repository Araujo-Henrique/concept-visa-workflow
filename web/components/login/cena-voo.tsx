"use client";

import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import { Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Logotipo } from "@/components/marca/logotipo";
import { ANEL, SETA } from "@/components/marca/simbolo";
import { useMovimento } from "@/components/provedores";

/**
 * Cena decorativa do login: um avião sai de Curitiba (sede da Concept) e voa até cada destino que a empresa
 * atende. Na chegada, cai o pin da logo com o tipo de visto. Com "reduzir movimento", a cena fica parada.
 */

const ORIGEM = { x: 190, y: 448, sigla: "CWB", cidade: "Curitiba" };
const DESTINOS = [
  { x: 560, y: 150, sigla: "JFK", cidade: "Nova York", pais: "EUA", visto: "Visto B1/B2" },
  { x: 410, y: 108, sigla: "YYZ", cidade: "Toronto", pais: "Canadá", visto: "eTA" },
  { x: 680, y: 452, sigla: "AKL", cidade: "Auckland", pais: "Nova Zelândia", visto: "NZeTA" },
] as const;

/** Arco de voo: curva quadrática com o ponto de controle erguido acima do meio do trajeto. */
export function rota(x0: number, y0: number, x1: number, y1: number): string {
  const distancia = Math.hypot(x1 - x0, y1 - y0);
  const cx = (x0 + x1) / 2;
  const cy = Math.min(y0, y1) - distancia * 0.28;
  return `M ${x0} ${y0} Q ${cx} ${cy} ${x1} ${y1}`;
}

const AVIAO =
  "M 18 0 L 6 -3 L -2 -14 L -7 -14 L -3 -3 L -12 -2 L -16 -7 L -19 -7 L -17 0 L -19 7 L -16 7 L -12 2 L -3 3 L -7 14 L -2 14 L 6 3 Z";

function Pin({ x, y, escala = 0.062 }: { x: number; y: number; escala?: number }) {
  const largura = 610 * escala;
  const altura = 725 * escala;
  return (
    <g transform={`translate(${x - largura / 2} ${y - altura}) scale(${escala})`}>
      <path d={ANEL} fill="#1d9d9d" />
      <path d={SETA} fill="#f5f5f5" />
    </g>
  );
}

function Etiqueta({ x, y, sigla, linha }: { x: number; y: number; sigla: string; linha: string }) {
  const largura = Math.max(118, linha.length * 6.6 + 24);
  return (
    <g transform={`translate(${x - largura / 2} ${y})`}>
      <rect width={largura} height={44} rx={10} fill="#0d0d1c" stroke="#1d9d9d" strokeOpacity={0.5} />
      <text
        x={12}
        y={19}
        fill="#f5f5f5"
        fontSize={14}
        fontWeight={800}
        letterSpacing={2}
        fontFamily="var(--font-montserrat)"
      >
        {sigla}
      </text>
      <text x={12} y={35} fill="#9fdede" fontSize={11} fontFamily="var(--font-inter)">
        {linha}
      </text>
    </g>
  );
}

export function CenaVoo() {
  // hidratação segura: no servidor e no 1º desenho do navegador, `reduzido` é sempre false
  const { reduzido: parado, preferencia, sistemaReduz, definir } = useMovimento();
  const paradoPeloSistema = parado && preferencia === "sistema" && sistemaReduz;

  const [indice, setIndice] = useState(0);
  const [chegou, setChegou] = useState(false);
  const progresso = useMotionValue(0);
  const caminho = useRef<SVGPathElement>(null);

  const destino = DESTINOS[indice];
  const d = rota(ORIGEM.x, ORIGEM.y, destino.x, destino.y);

  // posição e direção do avião ao longo da rota
  const ponto = (t: number) => {
    const p = caminho.current;
    if (!p) return { x: ORIGEM.x, y: ORIGEM.y, angulo: 0 };
    const total = p.getTotalLength();
    const a = p.getPointAtLength(Math.max(0, t * total - 1));
    const b = p.getPointAtLength(Math.min(total, t * total + 1));
    return {
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2,
      angulo: (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI,
    };
  };
  const x = useTransform(progresso, (t) => ponto(t).x);
  const y = useTransform(progresso, (t) => ponto(t).y);
  const rotate = useTransform(progresso, (t) => ponto(t).angulo);
  const opacidade = useTransform(progresso, [0, 0.9, 1], [1, 1, 0]); // o avião "pousa" e dá lugar ao pin

  useEffect(() => {
    if (parado) {
      progresso.set(1); // motion value, não estado: a cena parada mostra a rota inteira
      return;
    }
    progresso.set(0);
    let espera: ReturnType<typeof setTimeout>;
    const voo = animate(progresso, 1, { duration: 2.6, ease: [0.45, 0, 0.25, 1] });
    voo.then(() => {
      setChegou(true);
      espera = setTimeout(() => {
        setChegou(false); // próximo voo: o pin anterior sai junto com a troca de destino
        setIndice((i) => (i + 1) % DESTINOS.length);
      }, 1900);
    });
    return () => {
      voo.stop();
      clearTimeout(espera);
    };
  }, [indice, parado, progresso]);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-tinta text-papel">
      {/* céu: brilho azul + grade de pontos */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(circle at 70% 30%, rgba(29,157,157,0.28), transparent 55%), radial-gradient(rgba(245,245,245,0.12) 1px, transparent 1px)",
          backgroundSize: "100% 100%, 22px 22px",
        }}
      />

      <div className="relative z-10 flex items-start justify-between gap-4 p-6 lg:p-12">
        <Logotipo claro className="text-xl lg:text-3xl" />
        {paradoPeloSistema && (
          // o sistema pediu menos movimento; a pessoa pode liberar só para este sistema
          <button
            type="button"
            onClick={() => definir("ligado")}
            className="inline-flex items-center gap-1.5 rounded-full border border-papel/20 px-3 py-1.5 text-xs text-papel/80 transition-colors hover:border-marca hover:text-papel"
          >
            <Play className="size-3" /> Ver animação
          </button>
        )}
      </div>

      {/* no celular a cena ganha altura própria; no computador ocupa o espaço que sobra */}
      <svg
        viewBox="0 0 800 600"
        className="relative z-0 -mt-6 h-56 w-full sm:h-72 lg:-mt-10 lg:h-auto lg:flex-1"
        aria-hidden
      >
        {/* meridianos de um globo, bem sutis */}
        <g fill="none" stroke="#f5f5f5" strokeOpacity={0.06}>
          {[120, 220, 320].map((r) => (
            <ellipse key={r} cx={430} cy={320} rx={r * 1.6} ry={r} />
          ))}
          <ellipse cx={430} cy={320} rx={40} ry={320} />
          <ellipse cx={430} cy={320} rx={220} ry={320} />
        </g>

        {/* rotas: todas tracejadas e fracas; a atual é desenhada pelo voo */}
        {DESTINOS.map((dst) => (
          <path
            key={dst.sigla}
            d={rota(ORIGEM.x, ORIGEM.y, dst.x, dst.y)}
            fill="none"
            stroke="#f5f5f5"
            strokeOpacity={0.18}
            strokeWidth={1.5}
            strokeDasharray="2 8"
            strokeLinecap="round"
          />
        ))}
        <path ref={caminho} d={d} fill="none" stroke="none" />
        <motion.path
          key={`rastro-${destino.sigla}`}
          d={d}
          fill="none"
          stroke="#1d9d9d"
          strokeWidth={2.5}
          strokeLinecap="round"
          style={{ pathLength: progresso }}
        />

        {/* origem */}
        <circle cx={ORIGEM.x} cy={ORIGEM.y} r={6} fill="#1d9d9d" />
        <circle cx={ORIGEM.x} cy={ORIGEM.y} r={14} fill="none" stroke="#1d9d9d" strokeOpacity={0.4} />
        <Etiqueta x={ORIGEM.x} y={ORIGEM.y + 22} sigla={ORIGEM.sigla} linha={`${ORIGEM.cidade} · sede`} />

        {/* destinos: o pin cai quando o avião chega */}
        <AnimatePresence>
          {(parado ? DESTINOS : chegou ? [destino] : []).map((dst) => (
            <motion.g
              key={dst.sigla}
              initial={{ y: -36, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.3 } }}
              transition={{ type: "spring", stiffness: 380, damping: 18 }}
            >
              <Pin x={dst.x} y={dst.y} />
              <Etiqueta x={dst.x} y={dst.y + 10} sigla={dst.sigla} linha={`${dst.cidade} · ${dst.visto}`} />
            </motion.g>
          ))}
        </AnimatePresence>

        {/* avião */}
        <motion.g style={{ x, y, rotate, opacity: opacidade }}>
          <path d={AVIAO} fill="#f5f5f5" />
        </motion.g>
      </svg>

      <div className="relative z-10 p-6 pt-0 lg:p-12 lg:pt-0">
        <p className="font-heading text-2xl font-extrabold leading-tight sm:text-3xl lg:text-4xl">
          Chega de burocracia.
          <span className="block text-marca">Do cadastro ao carimbo.</span>
        </p>
        <ul
          className="mt-5 hidden flex-wrap gap-2 text-xs font-medium sm:flex"
          aria-label="Destinos atendidos"
        >
          {DESTINOS.map((dst, i) => (
            <li
              key={dst.sigla}
              className={`rounded-full border px-3 py-1 transition-colors ${
                i === indice && !parado
                  ? "border-marca bg-marca/15 text-papel"
                  : "border-papel/15 text-papel/60"
              }`}
            >
              {dst.pais} · {dst.visto}
            </li>
          ))}
          <li className="rounded-full border border-papel/15 px-3 py-1 text-papel/60">Passaporte</li>
        </ul>
      </div>
    </div>
  );
}
