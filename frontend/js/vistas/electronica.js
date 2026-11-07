import { api, descargar } from "../api.js";
import {
  abrirDialogo, alerta, anexar, aviso, CONCEPTOS_NOTA, fechaHora, h, pesos, seleccion, sello, TIPOS_DOCUMENTO, campo,
} from "../ui.js";
import { vacio } from "./pacientes.js";
import { abrirFactura } from "./facturas.js";

const nombreArchivo = (doc) => `${doc.numero}.xml`;

export async function bajarXml(doc) {
  try {
    await descargar(`/api/electronica/documentos/${doc.id}/xml`, nombreArchivo(doc));
  } catch (error) {
    aviso(error.message, "error");
  }
}

// Detalle de un documento electrónico: adquirente, CUFE/CUDE, línea de tiempo de estados y XML.
export function abrirDocumento(doc, { alCambiar = () => {}, puedeOperar = false } = {}) {
  abrirDialogo({
    titulo: `${TIPOS_DOCUMENTO[doc.tipo]} ${doc.numero}`,
    ancho: true,
    construir: (cuerpo, cerrar) => pintar(cuerpo, cerrar, doc),
  });

  function pintar(cuerpo, cerrar, d) {
    const dato = (t, v) => h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
    const mensaje = h("div");
    const acciones = h("div", { class: "acciones no-imprimir" });
    if (puedeOperar && d.tipo === "FACTURA" && d.estado === "RECHAZADO") {
      const boton = h("button", { class: "btn btn-primario", type: "button" }, "Reintentar el envío");
      boton.addEventListener("click", async () => {
        boton.disabled = true;
        try {
          const nuevo = await api.post(`/api/electronica/documentos/${d.id}/reintentar`);
          aviso(nuevo.estado === "ACEPTADO" ? "Documento aceptado." : "El documento sigue rechazado.", nuevo.estado === "ACEPTADO" ? "ok" : "error");
          alCambiar(nuevo);
          pintar(cuerpo, cerrar, nuevo);
        } catch (error) {
          mensaje.replaceChildren(alerta(error));
          boton.disabled = false;
        }
      });
      anexar(acciones, [boton]);
    }
    anexar(acciones, [
      h("button", { class: "btn", type: "button", onclick: () => bajarXml(d) }, "Descargar XML"),
      h("button", { class: "btn", type: "button", onclick: () => { cerrar(); verFactura(d, alCambiar); } }, `Ver factura ${d.factura_numero}`),
    ]);
    cuerpo.replaceChildren();
    anexar(cuerpo, [
      mensaje,
      h("dl", { class: "ficha" },
        dato("Documento", d.numero), dato("Fecha", d.fecha ? fechaHora(d.fecha) : ""),
        dato("Adquirente", d.adquirente_nombre),
        dato(d.adquirente_es_pagador ? "NIT" : "Documento", d.adquirente_documento + (d.adquirente_dv ? `-${d.adquirente_dv}` : "")),
        dato("Paciente", d.paciente_nombre), dato("Valor del documento", pesos(d.valor)),
        d.tipo === "NOTA_CREDITO" ? dato("Concepto", CONCEPTOS_NOTA[d.concepto]) : null,
        d.motivo ? dato("Motivo", d.motivo) : null,
        h("div", {}, h("dt", {}, "Estado"), h("dd", {}, sello(d.estado)))),
      h("div", { class: d.estado === "RECHAZADO" ? "alerta" : "nota-dian", role: d.estado === "RECHAZADO" ? "alert" : null },
        h("b", {}, `Respuesta (${d.codigo_respuesta || "—"}): `), d.mensaje_respuesta || "—"),
      h("section", { class: "subseccion" }, h("h3", {}, d.tipo === "FACTURA" ? "CUFE" : "CUDE"), h("code", { class: "cufe" }, d.cufe)),
      h("section", { class: "subseccion" }, h("h3", {}, "Historial del documento"),
        h("ol", { class: "linea-tiempo" }, d.eventos.map((e) => h("li", {},
          h("span", { class: "fecha" }, fechaHora(e.fecha)), sello(e.estado), h("span", {}, e.mensaje))))),
      h("section", { class: "subseccion" }, h("h3", {}, "Texto del código QR"), h("pre", { class: "qr-texto" }, d.qr)),
      acciones]);
  }
}

async function verFactura(doc, alCambiar) {
  try {
    abrirFactura(await api.get(`/api/facturas/${doc.factura_id}`), { puedeOperar: true, puedeCartera: true, alCambiar });
  } catch (error) {
    aviso(error.message, "error");
  }
}

// Pantalla de facturación electrónica: pendientes por emitir y documentos ya generados.
export async function montarElectronica(raiz, { usuario }) {
  const puedeOperar = usuario.rol === "RECEPCION";
  const tipo = seleccion("tipo", [["", "Todos"], ["FACTURA", "Facturas electrónicas"], ["NOTA_CREDITO", "Notas crédito"]], "");
  const estado = seleccion("estado", [["", "Todos"], ["ACEPTADO", "Aceptados"], ["RECHAZADO", "Rechazados"]], "");
  const zona = h("div", { "aria-live": "polite" });
  const info = await api.get("/api/electronica/proveedor");

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando documentos…"));
    try {
      const [docs, facturas] = await Promise.all([api.get("/api/electronica/documentos"), api.get("/api/facturas")]);
      const conFactura = new Set(docs.filter((d) => d.tipo === "FACTURA").map((d) => d.factura_id));
      const pendientes = facturas.filter((f) => f.estado !== "ANULADA" && !conFactura.has(f.id));
      const lista = docs.filter((d) => (!tipo.value || d.tipo === tipo.value) && (!estado.value || d.estado === estado.value));
      const rechazados = docs.filter((d) => d.estado === "RECHAZADO" && d.tipo === "FACTURA").length;
      zona.replaceChildren(...[
        h("div", { class: "resumen-cifras" },
          cifra("Por emitir", String(pendientes.length), pendientes.length ? "pendiente" : "ok"),
          cifra("Aceptados", String(docs.filter((d) => d.estado === "ACEPTADO").length), "ok"),
          cifra("Rechazados", String(rechazados), rechazados ? "alerta" : ""),
          cifra("Notas crédito", String(docs.filter((d) => d.tipo === "NOTA_CREDITO").length), "")),
        pendientes.length ? tablaPendientes(pendientes) : null,
        h("section", { class: "subseccion" },
          h("h2", {}, "Documentos generados"),
          h("div", { class: "barra" }, campo("Tipo", tipo), campo("Estado", estado)),
          lista.length ? tablaDocumentos(lista) : vacio(docs.length ? "No hay documentos con ese filtro." : "Todavía no se ha emitido ningún documento electrónico."))].filter(Boolean));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  function tablaPendientes(pendientes) {
    return h("section", { class: "subseccion" },
      h("h2", {}, "Facturas por emitir"),
      h("p", { class: "suave" }, info.obligatoria
        ? "Una factura con pagador no se puede radicar mientras su factura electrónica no esté aceptada."
        : "La emisión electrónica es opcional en este momento."),
      h("div", { class: "tabla-contenedor" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Factura", "Paciente", "Se factura a", "Valor", ""].map((t, i) => h("th", { class: i === 3 ? "num" : "" }, t)))),
        h("tbody", {}, pendientes.map((f) => {
          const aPagador = f.valor_pagador > 0;
          const boton = h("button", { class: "btn btn-pequeno btn-primario", type: "button" }, "Emitir");
          boton.addEventListener("click", async () => {
            boton.disabled = true;
            try {
              const doc = await api.post(`/api/electronica/facturas/${f.id}/emitir`);
              aviso(doc.estado === "ACEPTADO" ? `Factura electrónica ${doc.numero} aceptada.` : `Factura ${doc.numero} rechazada: revise el detalle.`, doc.estado === "ACEPTADO" ? "ok" : "error");
              await cargar();
              if (doc.estado !== "ACEPTADO") abrirDocumento(doc, { alCambiar: cargar, puedeOperar });
            } catch (error) {
              aviso(error.message, "error");
              boton.disabled = false;
            }
          });
          return h("tr", {},
            h("td", { class: "num-izq" }, h("b", {}, f.numero)), h("td", {}, f.paciente_nombre),
            h("td", {}, aPagador ? f.pagador_nombre : "Paciente (particular)"),
            h("td", { class: "num" }, pesos(aPagador ? f.valor_pagador : f.valor_paciente)),
            h("td", {}, puedeOperar ? boton : null));
        })))));
  }

  function tablaDocumentos(lista) {
    return h("div", { class: "tabla-contenedor" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Documento", "Tipo", "Fecha", "Adquirente", "Valor", "Estado", ""].map((t, i) => h("th", { class: i === 4 ? "num" : "" }, t)))),
      h("tbody", {}, lista.map((d) => h("tr", {},
        h("td", { class: "num-izq" }, h("b", {}, d.numero), h("div", { class: "suave pequeno" }, d.factura_numero)),
        h("td", {}, TIPOS_DOCUMENTO[d.tipo]), h("td", { class: "fecha" }, d.fecha ? fechaHora(d.fecha) : "—"),
        h("td", {}, d.adquirente_nombre), h("td", { class: "num" }, pesos(d.valor)), h("td", {}, sello(d.estado)),
        h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirDocumento(d, { alCambiar: cargar, puedeOperar }) }, "Ver")))))));
  }

  tipo.addEventListener("change", cargar);
  estado.addEventListener("change", cargar);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Facturación electrónica"),
        h("p", {}, "Facturas y notas crédito con CUFE/CUDE, XML y estado ante el proveedor tecnológico."))),
    h("div", { class: "alerta aviso-simulado", role: "note" },
      h("b", {}, "Modo de demostración. "),
      `${info.proveedor}. Ambiente: ${info.ambiente}. Resolución ${info.resolucion}, prefijo ${info.prefijo}, rango ${info.rango_desde}–${info.rango_hasta}. `,
      "Los documentos no se transmiten a la DIAN ni llevan firma electrónica."),
    zona);
  await cargar();
}

function cifra(titulo, valor, tono) {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}
