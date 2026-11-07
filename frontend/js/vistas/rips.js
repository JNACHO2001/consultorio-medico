import { api } from "../api.js";
import { alerta, aviso, campo, entrada, h, hoyISO, pesos, seleccion } from "../ui.js";
import { vacio } from "./pacientes.js";

function cifra(titulo, valor, tono = "") {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}

// Borrador del RIPS: reúne por factura al usuario y sus servicios y señala lo que falta antes de reportarlo.
export async function montarRips(raiz) {
  const pagadores = await api.get("/api/pagadores");
  const hoy = hoyISO();
  const desde = entrada("desde", { tipo: "date", valor: `${hoy.slice(0, 8)}01`, requerido: true });
  const hasta = entrada("hasta", { tipo: "date", valor: hoy, requerido: true });
  const pagador = seleccion("pagador_id", [["", "Todos los pagadores"], ...pagadores.filter((p) => p.codigo !== "PARTICULAR").map((p) => [p.id, p.nombre])], "");
  const zona = h("div", { "aria-live": "polite" });
  let ultimo = null;

  const generar = h("button", { class: "btn btn-primario", type: "submit" }, "Generar borrador");
  const descargar = h("button", { class: "btn", type: "button", disabled: true }, "Descargar JSON");
  descargar.addEventListener("click", () => {
    if (!ultimo) return;
    const enlace = h("a", {
      href: URL.createObjectURL(new Blob([JSON.stringify(ultimo, null, 2)], { type: "application/json" })),
      download: `rips_borrador_${ultimo.periodo.desde}_${ultimo.periodo.hasta}.json`,
    });
    document.body.append(enlace);
    enlace.click();
    setTimeout(() => { URL.revokeObjectURL(enlace.href); enlace.remove(); }, 0);
    aviso("Borrador descargado.");
  });

  const form = h("form", {
    class: "barra",
    onsubmit: async (e) => {
      e.preventDefault();
      generar.disabled = true;
      zona.replaceChildren(h("p", { class: "cargando" }, "Generando…"));
      try {
        ultimo = await api.get("/api/rips", { desde: desde.value, hasta: hasta.value, pagador_id: pagador.value });
        descargar.disabled = false;
        pintar(ultimo);
      } catch (error) {
        ultimo = null;
        descargar.disabled = true;
        zona.replaceChildren(alerta(error));
      } finally {
        generar.disabled = false;
      }
    },
  }, campo("Desde", desde), campo("Hasta", hasta), campo("Pagador", pagador), generar, descargar);

  function pintar(r) {
    const s = r.resumen;
    zona.replaceChildren(
      s.facturas
        ? h("div", {},
          h("div", { class: `alerta ${s.listoParaReportar ? "ok" : "info"}` },
            s.listoParaReportar
              ? h("span", {}, h("b", {}, "Sin errores. "), "El borrador no tiene faltantes que impidan reportarlo.")
              : h("span", {}, h("b", {}, `${s.errores} ${s.errores === 1 ? "error" : "errores"} por corregir. `), "Corrija los datos y genere el borrador de nuevo.")),
          h("div", { class: "resumen-cifras" },
            cifra("Facturas incluidas", String(s.facturas)), cifra("Valor a cargo de pagadores", pesos(s.valorFacturado)),
            cifra("Errores", String(s.errores), s.errores ? "pendiente" : "ok"), cifra("Avisos", String(s.avisos))),
          r.inconsistencias.length ? tablaInconsistencias(r.inconsistencias) : null,
          h("section", { class: "panel" }, h("h2", {}, "Facturas del borrador"),
            h("div", { class: "tabla-contenedor" }, h("table", {},
              h("thead", {}, h("tr", {}, ["Factura", "Pagador", "Usuario", "Servicios", "A cargo del pagador"].map((t, i) => h("th", { class: i === 4 ? "num" : "" }, t)))),
              h("tbody", {}, r.facturas.map((f) => h("tr", {},
                h("td", { class: "num-izq" }, h("b", {}, f.numFactura)), h("td", {}, f.pagador.nombre),
                h("td", { class: "num" }, `${f.usuario.tipoDocumentoIdentificacion || ""} ${f.usuario.numDocumentoIdentificacion || ""}`),
                h("td", { class: "num" }, String(Object.values(f.servicios).reduce((t, l) => t + l.length, 0))),
                h("td", { class: "num" }, pesos(f.valorPagador))))))),
            h("p", { class: "suave pequeno", style: "margin-top:.8rem" }, "Es un borrador con la estructura general del RIPS. La validación oficial ante el Ministerio de Salud no está incluida.")))
        : vacio("No hay facturas a cargo de pagadores en ese periodo."));
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "RIPS"),
        h("p", {}, "Registro individual de prestación de servicios: genere el borrador del periodo y corrija lo que falte antes de reportarlo."))),
    h("section", { class: "panel" }, form, zona));
}

function tablaInconsistencias(lista) {
  return h("section", { class: "panel", style: "margin-bottom:1rem" }, h("h2", {}, "Inconsistencias"),
    h("div", { class: "tabla-contenedor" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Nivel", "Factura", "Problema", "Qué hacer"].map((t) => h("th", {}, t)))),
      h("tbody", {}, lista.map((i) => h("tr", {},
        h("td", {}, h("span", { class: `sello ${i.nivel === "ERROR" ? "anulada" : "emitida"}` }, i.nivel === "ERROR" ? "Error" : "Aviso")),
        h("td", { class: "num-izq" }, i.factura), h("td", {}, i.mensaje), h("td", { class: "suave" }, ayuda(i.codigo))))))));
}

function ayuda(codigo) {
  return {
    SIN_DIAGNOSTICO: "El médico tratante registra el diagnóstico CIE-10 en la cuenta del ingreso.",
    SIN_CUPS: "El administrador agrega el código CUPS en el catálogo de procedimientos.",
    USUARIO_INCOMPLETO: "Complete fecha de nacimiento y sexo en la ficha del paciente.",
    NO_RADICADA: "Radique la factura desde Cartera.",
  }[codigo] || "";
}
