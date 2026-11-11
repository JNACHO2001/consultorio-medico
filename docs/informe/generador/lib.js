// Utilidades para armar el informe Word (docx-js): texto con marcas, tablas en blanco y negro,
// figuras con numeración APA 7 y registro de títulos para el índice.
const fs = require("fs");
const path = require("path");
const {
  Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, HeadingLevel, AlignmentType, BorderStyle,
  WidthType, ShadingType, LevelFormat, PageBreak, PositionalTab, PositionalTabAlignment,
  PositionalTabRelativeTo, PositionalTabLeader, Footer, PageNumber, TabStopType, LeaderType,
} = require("docx");

const FUENTE = "Arial";
const MONO = "Courier New";
const ANCHO_UTIL = 9360; // Carta con márgenes de 1 pulgada (DXA)
const NEGRO = "000000";

const titulos = []; // {nivel, texto} en orden, para el índice
let nTabla = 0;
let nFigura = 0;

// ---------- texto con marcas: **negrita**, *cursiva*, `código`
function runs(texto, base = {}) {
  const partes = String(texto).split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g).filter((p) => p !== "");
  return partes.map((p) => {
    if (p.startsWith("**")) return new TextRun({ text: p.slice(2, -2), bold: true, font: FUENTE, color: NEGRO, ...base });
    if (p.startsWith("`")) return new TextRun({ text: p.slice(1, -1), font: MONO, color: NEGRO, ...base, size: (base.size || 22) - 2 });
    if (p.startsWith("*")) return new TextRun({ text: p.slice(1, -1), italics: true, font: FUENTE, color: NEGRO, ...base });
    return new TextRun({ text: p, font: FUENTE, color: NEGRO, ...base });
  });
}

function P(texto, opciones = {}) {
  const { size, bold, italics, ...resto } = opciones;
  return new Paragraph({
    children: runs(texto, { size: size || 22, bold, italics }),
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 120, line: 300 },
    ...resto,
  });
}

function H1(texto, { salto = false } = {}) {
  titulos.push({ nivel: 1, texto });
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: salto,
    children: [new TextRun({ text: texto, font: FUENTE, color: NEGRO })],
  });
}
function H2(texto) {
  titulos.push({ nivel: 2, texto });
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: texto, font: FUENTE, color: NEGRO })] });
}
function H3(texto) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: texto, font: FUENTE, color: NEGRO })] });
}

function viñetas(items, referencia = "vinetas") {
  return items.map(
    (t) =>
      new Paragraph({
        numbering: { reference: referencia, level: 0 },
        children: runs(t, { size: 22 }),
        alignment: AlignmentType.JUSTIFIED,
        spacing: { after: 60, line: 290 },
      })
  );
}

function codigo(lineas) {
  return lineas.map(
    (l, i) =>
      new Paragraph({
        children: [new TextRun({ text: l === "" ? " " : l, font: MONO, size: 17, color: NEGRO })],
        shading: { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" },
        spacing: { after: 0, line: 240 },
        indent: { left: 200, right: 200 },
        keepLines: true,
        keepNext: i < lineas.length - 1,
      })
  );
}

// ---------- tablas (blanco y negro; encabezado en gris claro)
const borde = { style: BorderStyle.SINGLE, size: 4, color: NEGRO };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };

function celda(texto, ancho, { cabecera = false, alinear = AlignmentType.LEFT, negrita = false } = {}) {
  const lineas = Array.isArray(texto) ? texto : [texto];
  return new TableCell({
    width: { size: ancho, type: WidthType.DXA },
    borders: bordes,
    shading: cabecera ? { type: ShadingType.CLEAR, fill: "D9D9D9", color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: lineas.map(
      (t) =>
        new Paragraph({
          alignment: alinear,
          spacing: { after: 20, line: 250 },
          children: runs(t, { size: 18, bold: cabecera || negrita }),
        })
    ),
  });
}

// Tabla APA 7: «Tabla n» en negrita, título en cursiva, tabla y nota opcional.
function tabla(titulo, encabezados, filas, anchos, { alinear = [], nota } = {}) {
  nTabla += 1;
  const suma = anchos.reduce((a, b) => a + b, 0);
  if (suma !== ANCHO_UTIL) throw new Error(`Los anchos de «${titulo}» suman ${suma}, no ${ANCHO_UTIL}`);
  const out = [
    new Paragraph({ children: runs(`**Tabla ${nTabla}**`, { size: 20 }), spacing: { before: 160, after: 0 }, keepNext: true }),
    new Paragraph({ children: runs(`*${titulo}*`, { size: 20 }), spacing: { after: 80 }, keepNext: true }),
    new Table({
      width: { size: ANCHO_UTIL, type: WidthType.DXA },
      columnWidths: anchos,
      rows: [
        new TableRow({
          tableHeader: true,
          cantSplit: true,
          children: encabezados.map((e, i) => celda(e, anchos[i], { cabecera: true, alinear: alinear[i] || AlignmentType.LEFT })),
        }),
        ...filas.map(
          (f) =>
            new TableRow({
              cantSplit: true,
              children: f.map((c, i) => celda(c, anchos[i], { alinear: alinear[i] || AlignmentType.LEFT })),
            })
        ),
      ],
    }),
  ];
  if (nota) out.push(new Paragraph({ children: runs(`*Nota.* ${nota}`, { size: 17 }), spacing: { before: 60, after: 160 } }));
  else out.push(new Paragraph({ children: [], spacing: { after: 120 } }));
  return out;
}

// ---------- figuras
function tamañoPng(ruta) {
  const b = fs.readFileSync(ruta);
  return { ancho: b.readUInt32BE(16), alto: b.readUInt32BE(20) };
}

function figura(titulo, ruta, anchoPx, nota) {
  nFigura += 1;
  const { ancho, alto } = tamañoPng(ruta);
  const alturaPx = Math.round((anchoPx * alto) / ancho);
  const out = [
    new Paragraph({ children: runs(`**Figura ${nFigura}**`, { size: 20 }), spacing: { before: 160, after: 0 }, keepNext: true }),
    new Paragraph({ children: runs(`*${titulo}*`, { size: 20 }), spacing: { after: 80 }, keepNext: true }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      keepNext: !!nota,
      spacing: { after: 60 },
      children: [
        new ImageRun({
          type: "png",
          data: fs.readFileSync(ruta),
          transformation: { width: anchoPx, height: alturaPx },
          altText: { title: `Figura ${nFigura}`, description: titulo, name: path.basename(ruta) },
        }),
      ],
    }),
  ];
  out.push(new Paragraph({ children: runs(nota ? `*Nota.* ${nota}` : " ", { size: 17 }), spacing: { after: 160 } }));
  return out;
}

function saltoDePagina() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ---------- índice estático (con los números de página calculados en una primera pasada)
function indice(paginas) {
  return titulos.map(
    (t) =>
      new Paragraph({
        spacing: { after: t.nivel === 1 ? 70 : 40, before: t.nivel === 1 ? 90 : 0 },
        indent: { left: t.nivel === 1 ? 0 : 400 },
        tabStops: [{ type: TabStopType.RIGHT, position: ANCHO_UTIL, leader: LeaderType.DOT }],
        children: [
          new TextRun({ text: t.texto, font: FUENTE, size: t.nivel === 1 ? 22 : 20, bold: t.nivel === 1, color: NEGRO }),
          new TextRun({ text: "\t" + String(paginas[t.texto] || "0"), font: FUENTE, size: t.nivel === 1 ? 22 : 20, bold: t.nivel === 1, color: NEGRO }),
        ],
      })
  );
}

function pie() {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Informe técnico · Arquitectura de Software · Unidad 2          Página ", font: FUENTE, size: 17, color: NEGRO }),
          new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 17, color: NEGRO }),
        ],
      }),
    ],
  });
}

const numeracion = {
  config: [
    {
      reference: "vinetas",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }],
    },
  ],
};

module.exports = {
  FUENTE, ANCHO_UTIL, NEGRO, titulos, runs, P, H1, H2, H3, viñetas, codigo, tabla, figura, saltoDePagina, indice, pie, numeracion,
  AlignmentType, celda, bordes,
};
