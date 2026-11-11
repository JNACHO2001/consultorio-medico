// Ensambla el informe Word (blanco y negro; diagramas y gráficas a color).
//   node generar_informe.js          -> ../Informe_Unidad2_Arquitectura_Distribuida.docx
// El índice usa los números de página de paginas.json, que calcula paginas.py (ver generar.sh).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, Footer,
} = require("docx");
const lib = require("./lib");
const seccionA = require("./seccion_a");
const seccionB = require("./seccion_b");

const { FUENTE, NEGRO, P, runs, celda, indice, pie, numeracion, saltoDePagina, titulos } = lib;
const parametros = JSON.parse(fs.readFileSync(path.join(__dirname, "parametros.json"), "utf-8"));
const rutaPaginas = path.join(__dirname, "paginas.json");
const paginas = fs.existsSync(rutaPaginas) ? JSON.parse(fs.readFileSync(rutaPaginas, "utf-8")) : {};

const centrado = (texto, { size = 22, bold = false, before = 0, after = 120, italics = false } = {}) =>
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before, after },
    children: [new TextRun({ text: texto, font: FUENTE, size, bold, italics, color: NEGRO })],
  });

function portada() {
  const anchos = [4400, 4960];
  const fila = (a, b, cab = false) =>
    new TableRow({ cantSplit: true, children: [celda(a, anchos[0], { cabecera: cab }), celda(b, anchos[1], { cabecera: cab })] });
  return [
    centrado("[Nombre de la universidad]", { size: 28, bold: true, before: 600, after: 100 }),
    centrado("Facultad o programa: [Nombre del programa]", { size: 22, after: 500 }),
    centrado("Arquitectura de Software", { size: 26, bold: true, after: 60 }),
    centrado("Unidad 2 · Mini proyecto (Aprendizaje Basado en Proyectos)", { size: 22, after: 700 }),
    centrado("Tejiendo redes: arquitectura de software entre hilos y nodos", { size: 36, bold: true, after: 160 }),
    centrado("Facturación electrónica distribuida para el consultorio médico «Salud Integral»", { size: 26, italics: true, after: 160 }),
    centrado("Informe técnico", { size: 24, after: 600 }),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: anchos,
      rows: [
        fila("**Integrante**", "**Rol asignado**", true),
        fila("José Ignacio Gómez Guzmán", "[Rol]"),
        fila("[Nombre del integrante 2]", "[Rol]"),
        fila("[Nombre del integrante 3]", "[Rol]"),
        fila("[Nombre del integrante 4]", "[Rol]"),
        fila("[Nombre del integrante 5 (si aplica)]", "[Rol]"),
      ],
    }),
    centrado("Docente: [Nombre del docente]", { size: 22, before: 500, after: 100 }),
    centrado("Fecha de entrega: 11 de noviembre de 2026", { size: 22, after: 100 }),
    centrado("Repositorio: https://github.com/JNACHO2001/consultorio-medico", { size: 19, before: 300, after: 40 }),
    centrado("Video: [enlace de YouTube no listado]", { size: 19, after: 0 }),
  ];
}

// 1) contenido (llena el registro de títulos)  2) índice con los números de página  3) documento
const contenido = [...seccionA(parametros), ...seccionB(parametros)];
const tituloIndice = new Paragraph({
  spacing: { after: 240 },
  children: [new TextRun({ text: "Índice", font: FUENTE, size: 30, bold: true, color: NEGRO })],
});

const doc = new Document({
  creator: "Equipo Salud Integral",
  title: "Tejiendo redes: arquitectura de software entre hilos y nodos — Informe técnico Unidad 2",
  styles: {
    default: { document: { run: { font: FUENTE, size: 22, color: NEGRO } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 30, bold: true, color: NEGRO },
        paragraph: { spacing: { before: 360, after: 200 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 25, bold: true, color: NEGRO },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 22, bold: true, italics: true, color: NEGRO },
        paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: numeracion,
  sections: [
    {
      properties: {
        titlePage: true,
        page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1300, left: 1440 } },
      },
      footers: { default: pie(), first: new Footer({ children: [new Paragraph({ children: [] })] }) },
      children: [...portada(), saltoDePagina(), tituloIndice, ...indice(paginas), ...contenido],
    },
  ],
});

const salida = path.resolve(__dirname, "../Informe_Unidad2_Arquitectura_Distribuida.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(salida, buffer);
  fs.writeFileSync(path.join(__dirname, "titulos.json"), JSON.stringify(titulos, null, 1), "utf-8");
  console.log("Informe escrito:", salida, `(${titulos.length} títulos en el índice)`);
});
