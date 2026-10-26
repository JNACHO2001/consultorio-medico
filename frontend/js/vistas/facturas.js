import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, areaTexto, aviso, campo, fechaHora, h, METODOS_PAGO, pesos, seleccion, sello,
} from "../ui.js";
import { vacio } from "./pacientes.js";

// Detalle de una factura en un diálogo. `puedeOperar` (recepción) habilita pagar y anular.
export function abrirFactura(factura, { puedeOperar = false, alCambiar = () => {} } = {}) {
  abrirDialogo({
    titulo: `Factura ${factura.numero}`,
    ancho: true,
    construir: (cuerpo, cerrar) => pintar(cuerpo, cerrar, factura),
  });

  function pintar(cuerpo, cerrar, f) {
    const mensaje = h("div");
    const dato = (t, v) => h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
    const acciones = h("div", { class: "acciones no-imprimir" });

    if (puedeOperar && f.estado === "EMITIDA") {
      const metodo = seleccion("metodo_pago", METODOS_PAGO, "EFECTIVO");
      const pagar = h("button", { class: "btn btn-primario", type: "button" }, "Registrar pago");
      pagar.addEventListener("click", async () => {
        pagar.disabled = true;
        try {
          const pagada = await api.post(`/api/facturas/${f.id}/pagar`, { metodo_pago: metodo.value });
          aviso("Pago registrado.");
          alCambiar(pagada);
          pintar(cuerpo, cerrar, pagada);
        } catch (error) {
          mensaje.replaceChildren(alerta(error));
          pagar.disabled = false;
        }
      });
      anexar(acciones, [
        h("div", { class: "pago" }, campo("Forma de pago", metodo), pagar),
        h("button", { class: "btn btn-peligro", type: "button", onclick: () => pedirAnulacion(f, cuerpo, cerrar) }, "Anular factura"),
      ]);
    }
    anexar(acciones, [h("button", { class: "btn", type: "button", onclick: () => window.print() }, "Imprimir")]);

    cuerpo.replaceChildren();
    anexar(cuerpo, [
      mensaje,
      h("dl", { class: "ficha" },
        dato("Paciente", f.paciente_nombre), dato("Documento", f.paciente_documento),
        dato("Fecha de emisión", f.fecha ? fechaHora(f.fecha) : ""), dato("Emitida por", f.emitida_por),
        h("div", {}, h("dt", {}, "Estado"), h("dd", {}, sello(f.estado))),
        f.estado === "PAGADA" ? dato("Pago", `${METODOS_PAGO.find(([v]) => v === f.metodo_pago)?.[1] || f.metodo_pago} · ${fechaHora(f.fecha_pago)}`) : null),
      f.estado === "ANULADA" ? h("div", { class: "alerta" }, h("b", {}, "Factura anulada. "), f.motivo_anulacion) : null,
      h("div", { class: "tabla-contenedor" }, h("table", { class: "cuenta" },
        h("thead", {}, h("tr", {}, ["Código", "Procedimiento", "Cant.", "Valor unitario", "Subtotal"].map((t, i) => h("th", { class: i > 1 ? "num" : "" }, t)))),
        h("tbody", {}, f.lineas.map((l) => h("tr", {},
          h("td", { class: "num-izq" }, l.codigo), h("td", {}, l.descripcion),
          h("td", { class: "num" }, l.cantidad), h("td", { class: "num" }, pesos(l.valor_unitario)), h("td", { class: "num" }, pesos(l.subtotal))))),
        h("tfoot", {}, h("tr", {}, h("th", { colspan: 4, class: "num" }, "Total"), h("th", { class: "num total" }, pesos(f.total)))))),
      acciones]);
  }

  function pedirAnulacion(f, cuerpoFactura, cerrarFactura) {
    abrirDialogo({
      titulo: `Anular ${f.numero}`,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const boton = h("button", { class: "btn btn-peligro", type: "submit" }, "Anular factura");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            boton.disabled = true;
            try {
              const anulada = await api.post(`/api/facturas/${f.id}/anular`, { motivo: form.elements.motivo.value.trim() });
              cerrar();
              aviso("Factura anulada. Sus procedimientos quedaron pendientes de facturar.");
              alCambiar(anulada);
              pintar(cuerpoFactura, cerrarFactura, anulada);
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              boton.disabled = false;
            }
          },
        }, mensaje,
          h("p", {}, "Los procedimientos volverán a quedar pendientes y podrán facturarse de nuevo. Una factura pagada no se puede anular."),
          campo("Motivo de la anulación", areaTexto("motivo", "", { rows: 2, required: true, maxlength: 300 })),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
        cuerpo.append(form);
      },
    });
  }
}

// Pantalla de facturación (recepción gestiona; el administrador solo consulta).
export async function montarFacturas(raiz, { usuario }) {
  const puedeOperar = usuario.rol === "RECEPCION";
  const filtro = seleccion("estado", [["", "Todas"], ["EMITIDA", "Por cobrar"], ["PAGADA", "Pagadas"], ["ANULADA", "Anuladas"]], "");
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando facturas…"));
    try {
      const todas = await api.get("/api/facturas");
      const suma = (estado) => todas.filter((f) => f.estado === estado).reduce((t, f) => t + f.total, 0);
      const lista = filtro.value ? todas.filter((f) => f.estado === filtro.value) : todas;
      zona.replaceChildren(
        h("div", { class: "resumen-cifras" },
          cifra("Por cobrar", pesos(suma("EMITIDA")), "pendiente"),
          cifra("Cobrado", pesos(suma("PAGADA")), "ok"),
          cifra("Facturas anuladas", String(todas.filter((f) => f.estado === "ANULADA").length), "")),
        lista.length
          ? h("div", { class: "tabla-contenedor" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Factura", "Fecha", "Paciente", "Total", "Estado", ""].map((t, i) => h("th", { class: i === 3 ? "num" : "" }, t)))),
            h("tbody", {}, lista.map((f) => h("tr", {},
              h("td", { class: "num-izq" }, h("b", {}, f.numero)), h("td", { class: "fecha" }, fechaHora(f.fecha)),
              h("td", {}, h("b", {}, f.paciente_nombre), h("div", { class: "suave pequeno num" }, f.paciente_documento)),
              h("td", { class: "num" }, pesos(f.total)), h("td", {}, sello(f.estado)),
              h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirFactura(f, { puedeOperar, alCambiar: cargar }) }, "Ver")))))))
          : vacio(todas.length ? "No hay facturas con ese estado." : "Todavía no se ha facturado nada. Las facturas se generan desde la cuenta de cada ingreso."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  filtro.addEventListener("change", cargar);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Facturación"),
        h("p", {}, puedeOperar ? "Facturas generadas desde la cuenta de cada ingreso: cobre, o anule las que tengan errores." : "Consulta de facturas y valores cobrados."))),
    h("section", { class: "panel" }, h("div", { class: "barra" }, campo("Mostrar", filtro)), zona));
  await cargar();
}

function cifra(titulo, valor, tono) {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}
