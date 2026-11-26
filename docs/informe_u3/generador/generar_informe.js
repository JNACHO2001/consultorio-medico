// Ensambla el informe Word de la Unidad 3 (blanco y negro).
//   node generar_informe.js  ->  ../Informe_Unidad3_Navegacion.docx
// El índice usa los números de página de paginas.json, que calcula paginas.py (ver generar.sh).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, AlignmentType, WidthType, Footer, ExternalHyperlink,
} = require("docx");
const lib = require("../../informe/generador/lib");
const contenido = require("./contenido");

const { FUENTE, NEGRO, P, runs, celda, indice, numeracion, saltoDePagina, titulos, H1, ANCHO_UTIL } = lib;

const RESULTADOS = path.resolve(__dirname, "../../../backend/benchmarks/resultados/resultados_navegacion.json");
const R = JSON.parse(fs.readFileSync(RESULTADOS, "utf-8"));
R.pruebas = JSON.parse(fs.readFileSync(path.join(__dirname, "parametros.json"), "utf-8")).pruebas;

const rutaPaginas = path.join(__dirname, "paginas.json");
const paginas = fs.existsSync(rutaPaginas) ? JSON.parse(fs.readFileSync(rutaPaginas, "utf-8")) : {};

const centrado = (texto, { size = 22, bold = false, before = 0, after = 120, italics = false } = {}) =>
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before, after },
    children: [new TextRun({ text: texto, font: FUENTE, size, bold, italics, color: NEGRO })],
  });

const ENLACE_VIDEO = "https://youtu.be/XXXXXXXXXXX";
const REPO = "https://github.com/JNACHO2001/consultorio-medico";

function enlace(texto, url, size = 20) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60 },
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text: texto, font: FUENTE, size, color: NEGRO, underline: {} })],
      }),
    ],
  });
}

function portada() {
  const anchos = [4400, 4960];
  const fila = (a, b, cab = false) =>
    new TableRow({ cantSplit: true, children: [celda(a, anchos[0], { cabecera: cab }), celda(b, anchos[1], { cabecera: cab })] });
  return [
    centrado("[Nombre de la institución]", { size: 28, bold: true, before: 500, after: 100 }),
    centrado("[Nombre del programa]", { size: 22, after: 420 }),
    centrado("Arquitectura de Software", { size: 26, bold: true, after: 60 }),
    centrado("Unidad 3 · Actividad 6 (Aprendizaje Basado en Proyectos)", { size: 22, after: 560 }),
    centrado("Navegando mareas: estrategias de navegación en la arquitectura de software", { size: 34, bold: true, after: 150 }),
    centrado("Navegación en catálogos extensos en el sistema de gestión clínica «Salud Integral»", { size: 24, italics: true, after: 140 }),
    centrado("Informe técnico", { size: 24, after: 480 }),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: anchos,
      rows: [
        fila("**Integrante**", "**Rol asignado**", true),
        fila("José Ignacio Gómez Guzmán", "[Rol]"),
        fila("[Nombre del integrante 2]", "[Rol]"),
        fila("[Nombre del integrante 3]", "[Rol]"),
        fila("[Nombre del integrante 4]", "[Rol]"),
      ],
    }),
    centrado("Docente: [Nombre del docente]", { size: 22, before: 440, after: 100 }),
    centrado("Fecha de entrega: [día] de [mes] de 2026", { size: 22, after: 300 }),
    centrado("Presentación oral en video (YouTube, no listado):", { size: 20, after: 40 }),
    enlace(ENLACE_VIDEO, ENLACE_VIDEO),
    centrado("Código fuente del prototipo:", { size: 20, before: 140, after: 40 }),
    enlace(REPO, REPO),
  ];
}

function referencias() {
  const refs = [
    "Bass, L., Clements, P., & Kazman, R. (2021). *Software architecture in practice* (4.ª ed.). Addison-Wesley.",
    "Card, S. K., Robertson, G. G., & Mackinlay, J. D. (1991). The information visualizer, an information workspace. En *Proceedings of the SIGCHI Conference on Human Factors in Computing Systems* (pp. 181–186). ACM. https://doi.org/10.1145/108844.108874",
    "Fielding, R. T. (2000). *Architectural styles and the design of network-based software architectures* [Tesis doctoral, University of California, Irvine].",
    "Fowler, M. (2002). *Patterns of enterprise application architecture*. Addison-Wesley.",
    "Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1995). *Design patterns: Elements of reusable object-oriented software*. Addison-Wesley.",
    "Krug, S. (2014). *Don't make me think, revisited: A common sense approach to web usability* (3.ª ed.). New Riders.",
    "Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press.",
    "Martin, R. C. (2017). *Clean architecture: A craftsman's guide to software structure and design*. Prentice Hall.",
    "Nielsen, J. (1993). *Usability engineering*. Morgan Kaufmann.",
    "Object Management Group. (2017). *OMG Unified Modeling Language (OMG UML), version 2.5.1*. https://www.omg.org/spec/UML/2.5.1/",
    "Organización Panamericana de la Salud. (2008). *Clasificación estadística internacional de enfermedades y problemas relacionados con la salud* (10.ª revisión, 3.ª ed.). OPS.",
    "Rumbaugh, J., Jacobson, I., & Booch, G. (2005). *The Unified Modeling Language reference manual* (2.ª ed.). Addison-Wesley.",
    "Tidwell, J., Brewer, C., & Valencia, A. (2020). *Designing interfaces: Patterns for effective interaction design* (3.ª ed.). O'Reilly Media.",
    "World Wide Web Consortium. (2018). *Web Content Accessibility Guidelines (WCAG) 2.1*. https://www.w3.org/TR/WCAG21/",
  ];
  return [
    H1("Referencias", { salto: true }),
    ...refs.map((r) =>
      new Paragraph({
        children: runs(r, { size: 22 }),
        alignment: AlignmentType.LEFT,
        spacing: { after: 140, line: 276 },
        indent: { left: 720, hanging: 720 },
      })
    ),
  ];
}

function pie() {
  const { PageNumber } = require("docx");
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Informe técnico · Arquitectura de Software · Unidad 3          Página ", font: FUENTE, size: 17, color: NEGRO }),
          new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 17, color: NEGRO }),
        ],
      }),
    ],
  });
}

const cuerpo = contenido(R);
const tituloIndice = new Paragraph({
  spacing: { after: 240 },
  children: [new TextRun({ text: "Índice", font: FUENTE, size: 30, bold: true, color: NEGRO })],
});

const doc = new Document({
  creator: "Equipo Salud Integral",
  title: "Navegando mareas: estrategias de navegación en la arquitectura de software — Informe técnico Unidad 3",
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
      children: [...portada(), saltoDePagina(), tituloIndice, ...indice(paginas), ...cuerpo, ...referencias()],
    },
  ],
});

const salida = path.resolve(__dirname, "../Informe_Unidad3_Navegacion.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(salida, buffer);
  fs.writeFileSync(path.join(__dirname, "titulos.json"), JSON.stringify(titulos, null, 1), "utf-8");
  console.log("Informe escrito:", salida, `(${titulos.length} títulos en el índice)`);
});
