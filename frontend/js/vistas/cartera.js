import { api } from "../api.js";
import { alerta, fechaHora, h, pesos, sello } from "../ui.js";
import { abrirFactura } from "./facturas.js";
import { vacio } from "./pacientes.js";

const TRAMOS = [
  ["sin_radicar", "Sin radicar"], ["d0_30", "0 a 30 días"], ["d31_60", "31 a 60 días"], ["d61_90", "61 a 90 días"], ["d_mas_90", "Más de 90 días"],
];

function cifra(titulo, valor, tono = "") {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}

// Cartera por pagador (lo que las EPS y aseguradoras deben a la IPS) o el detalle de uno de ellos.
export async function montarCartera(raiz, { usuario, parametros }) {
  const pagadorId = parametros[0] ? Number(parametros[0]) : null;
  return pagadorId ? detalle(raiz, usuario, pagadorId) : resumen(raiz);
}

async function resumen(raiz) {
  const lista = await api.get("/api/cartera");
  const total = (campo) => lista.reduce((t, r) => t + r[campo], 0);
  const tramo = (clave) => lista.reduce((t, r) => t + r.tramos[clave], 0);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Cartera"),
        h("p", {}, "Lo que cada pagador debe a la IPS, según los días desde la radicación de sus facturas."))),
    h("div", { class: "resumen-cifras" },
      cifra("Cartera total", pesos(total("saldo")), "pendiente"),
      cifra("En disputa por glosas", pesos(total("en_disputa")), total("en_disputa") ? "pendiente" : ""),
      cifra("Recaudado", pesos(total("recaudado")), "ok"),
      cifra("Glosas aceptadas", pesos(total("glosa_aceptada")))),
    h("section", { class: "panel" },
      h("h2", {}, "Antigüedad de la cartera"),
      lista.length
        ? h("div", { class: "tabla-contenedor" }, h("table", { class: "sin-corte" },
          h("thead", {}, h("tr", {}, ["Pagador", "Facturas", "Facturado", "Recaudado", ...TRAMOS.map(([, t]) => t), "Saldo", ""].map((t, i) => h("th", { class: i >= 1 && i <= 10 ? "num" : "" }, t)))),
          h("tbody", {}, lista.map((r) => h("tr", {},
            h("td", {}, h("b", {}, r.pagador_nombre)), h("td", { class: "num" }, r.n_facturas),
            h("td", { class: "num" }, pesos(r.facturado)), h("td", { class: "num" }, pesos(r.recaudado)),
            ...TRAMOS.map(([k]) => h("td", { class: `num ${k === "d_mas_90" && r.tramos[k] ? "vencida" : ""}` }, r.tramos[k] ? pesos(r.tramos[k]) : "—")),
            h("td", { class: "num" }, h("b", {}, pesos(r.saldo))),
            h("td", {}, h("a", { class: "btn btn-pequeno btn-primario", href: `#/cartera/${r.pagador_id}` }, "Ver facturas"))))),
          h("tfoot", {}, h("tr", {},
            h("th", {}, "Total"), h("th", { class: "num" }, lista.reduce((t, r) => t + r.n_facturas, 0)),
            h("th", { class: "num" }, pesos(total("facturado"))), h("th", { class: "num" }, pesos(total("recaudado"))),
            ...TRAMOS.map(([k]) => h("th", { class: "num" }, pesos(tramo(k)))),
            h("th", { class: "num" }, pesos(total("saldo"))), h("th")))))
        : vacio("Aún no hay facturas a cargo de pagadores. Aparecen cuando se factura un ingreso admitido con una EPS o aseguradora.")));
}

async function detalle(raiz, usuario, pagadorId) {
  const zona = h("div", { "aria-live": "polite" });
  const puedeOperar = usuario.rol === "RECEPCION";
  raiz.append(h("a", { class: "btn btn-enlace", href: "#/cartera" }, "‹ Volver a la cartera"), zona);

  async function cargar() {
    const { resumen: r, facturas } = await api.get(`/api/cartera/${pagadorId}`);
    const nombre = r?.pagador_nombre || facturas[0]?.pagador_nombre || "Pagador";
    zona.replaceChildren(
      h("header", { class: "encabezado", style: "margin-top:.6rem" }, h("div", {}, h("h1", {}, nombre), h("p", {}, "Facturas a cargo de este pagador."))),
      r ? h("div", { class: "resumen-cifras" },
        cifra("Saldo del pagador", pesos(r.saldo), "pendiente"), cifra("En disputa por glosas", pesos(r.en_disputa), r.en_disputa ? "pendiente" : ""),
        cifra("Recaudado", pesos(r.recaudado), "ok"), cifra("Más de 90 días", pesos(r.tramos.d_mas_90), r.tramos.d_mas_90 ? "pendiente" : "")) : null,
      h("section", { class: "panel" },
        facturas.length
          ? h("div", { class: "tabla-contenedor" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Factura", "Paciente", "Radicación", "A cargo del pagador", "Abonado", "Glosa", "Saldo", "Estado", ""].map((t, i) => h("th", { class: i >= 3 && i <= 6 ? "num" : "" }, t)))),
            h("tbody", {}, facturas.map((f) => h("tr", {},
              h("td", { class: "num-izq" }, h("b", {}, f.numero)),
              h("td", {}, f.paciente_nombre, h("div", { class: "suave pequeno num" }, f.paciente_documento)),
              h("td", { class: "fecha" }, f.fecha_radicacion ? [fechaHora(f.fecha_radicacion), h("div", { class: "suave pequeno" }, `${f.dias_radicada} d · ${f.numero_radicacion}`)] : h("span", { class: "sello emitida" }, "Sin radicar")),
              h("td", { class: "num" }, pesos(f.valor_pagador)), h("td", { class: "num" }, pesos(f.pagado_pagador)),
              h("td", { class: "num" }, f.glosa_en_disputa || f.glosado_aceptado ? [f.glosa_en_disputa ? h("div", {}, pesos(f.glosa_en_disputa), h("small", { class: "suave" }, " en disputa")) : null, f.glosado_aceptado ? h("div", { class: "suave pequeno" }, `${pesos(f.glosado_aceptado)} aceptada`) : null] : "—"),
              h("td", { class: "num" }, h("b", {}, pesos(f.saldo_pagador))), h("td", {}, sello(f.estado)),
              h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirFactura(f, { puedeOperar, puedeCartera: true, alCambiar: cargar }) }, "Gestionar")))))))
          : vacio("Este pagador no tiene facturas.")));
  }

  try {
    await cargar();
  } catch (error) {
    zona.replaceChildren(alerta(error));
  }
}
