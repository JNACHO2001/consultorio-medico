import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, areaTexto, aviso, campo, confirmar, datosDe, entrada, fechaHora, h, pesos, seleccion, sello, TIPOS_INGRESO,
} from "../ui.js";
import { abrirAdmision } from "./admision.js";
import { abrirFactura } from "./facturas.js";
import { vacio } from "./pacientes.js";

// ------------------------------------------------------------------ lista de ingresos

export async function montarIngresos(raiz, { usuario }) {
  const esMedico = usuario.rol === "MEDICO";
  const filtro = seleccion("estado", [["ABIERTO", "Abiertos"], ["EGRESADO", "Con egreso"], ["", "Todos"]], "ABIERTO");
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando ingresos…"));
    try {
      const lista = await api.get("/api/ingresos", { estado: filtro.value, medico_id: esMedico ? usuario.id : "" });
      zona.replaceChildren(lista.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Paciente", "Ingreso", esMedico ? "Motivo" : "Médico", "Estado", "Proced.", "Total", "Por facturar", ""].map((t, i) => h("th", { class: i >= 4 && i <= 6 ? "num" : "" }, t)))),
          h("tbody", {}, lista.map((i) => h("tr", {},
            h("td", {}, h("b", {}, i.paciente_nombre), h("div", { class: "suave pequeno num" }, i.paciente_documento)),
            h("td", { class: "fecha" }, fechaHora(i.fecha_ingreso), h("div", { class: "suave pequeno" }, TIPOS_INGRESO[i.tipo])),
            h("td", {}, esMedico ? i.motivo : i.medico_nombre),
            h("td", {}, sello(i.estado)),
            h("td", { class: "num" }, i.n_procedimientos), h("td", { class: "num" }, pesos(i.total)),
            h("td", { class: "num" }, i.pendiente_facturar ? h("b", {}, pesos(i.pendiente_facturar)) : "—"),
            h("td", {}, h("a", { class: "btn btn-pequeno btn-primario", href: `#/ingreso/${i.id}` }, "Abrir cuenta")))))))
        : vacio(filtro.value === "ABIERTO"
          ? (esMedico ? "No tiene pacientes ingresados en este momento." : "No hay pacientes ingresados. Use «Ingresar paciente» para abrir una cuenta.")
          : "No hay ingresos para mostrar."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  filtro.addEventListener("change", cargar);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, esMedico ? "Mis pacientes ingresados" : "Ingresos"),
        h("p", {}, esMedico ? "Registre los procedimientos realizados; quedan en la historia clínica y en la cuenta del paciente."
          : "Cada ingreso abre una cuenta a la que se cargan los procedimientos para facturarlos.")),
      esMedico ? null : h("button", { class: "btn btn-primario", type: "button", onclick: () => abrirAdmision({ alCrear: (i) => { window.location.hash = `#/ingreso/${i.id}`; } }) }, "Ingresar paciente")),
    h("section", { class: "panel" }, h("div", { class: "barra" }, campo("Mostrar", filtro)), zona));
  await cargar();
}

// ------------------------------------------------------------------ cuenta de un ingreso

export async function montarIngreso(raiz, { usuario, parametros }) {
  const id = Number(parametros[0]);
  const esMedico = usuario.rol === "MEDICO";
  const zona = h("div");
  raiz.append(h("a", { class: "btn btn-enlace", href: "#/ingresos" }, "‹ Volver a ingresos"), zona);
  await pintar();

  async function pintar() {
    const ingreso = await api.get(`/api/ingresos/${id}`);
    const [paciente, facturas] = await Promise.all([
      api.get(`/api/pacientes/${ingreso.paciente_id}`),
      esMedico ? [] : api.get("/api/facturas", { ingreso_id: id }),
    ]);
    const propio = esMedico && ingreso.medico_id === usuario.id;
    const abierto = ingreso.estado === "ABIERTO";
    const pendientes = ingreso.procedimientos.filter((p) => !p.anulado && !p.factura_id);

    const acciones = [];
    if (propio && abierto) {
      acciones.push(
        h("button", { class: "btn btn-primario", type: "button", onclick: () => registrar(ingreso) }, "Registrar procedimiento"),
        h("button", { class: "btn", type: "button", onclick: () => egreso(ingreso) }, "Dar egreso"));
    }
    if (!esMedico && pendientes.length) {
      acciones.push(h("button", { class: "btn btn-primario", type: "button", onclick: () => facturar(ingreso, pendientes) }, `Facturar pendientes (${pesos(ingreso.pendiente_facturar)})`));
    }

    zona.replaceChildren();
    anexar(zona, [
      h("header", { class: "encabezado", style: "margin-top:.6rem" },
        h("div", {}, h("h1", {}, ingreso.paciente_nombre),
          h("p", { class: "num" }, `${ingreso.paciente_documento}${paciente.eps ? " · " + paciente.eps : ""}`)),
        h("div", { class: "acciones", style: "margin:0;align-items:center" }, sello(ingreso.estado), ...acciones)),
      paciente.alergias ? h("div", { class: "alergias" }, h("b", {}, "Alergias: "), paciente.alergias) : null,
      h("section", { class: "panel" },
        h("dl", { class: "ficha" },
          dato("Tipo de ingreso", TIPOS_INGRESO[ingreso.tipo]), dato("Fecha de ingreso", fechaHora(ingreso.fecha_ingreso)),
          dato("Médico tratante", ingreso.medico_nombre), dato("Motivo", ingreso.motivo),
          ingreso.fecha_egreso ? dato("Fecha de egreso", fechaHora(ingreso.fecha_egreso)) : null,
          ingreso.resumen_egreso ? dato("Resumen de egreso", ingreso.resumen_egreso) : null)),
      cuenta(ingreso, propio && abierto),
      esMedico ? null : panelFacturas(facturas)]);
  }

  function dato(t, v) {
    return h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
  }

  function cuenta(ingreso, puedeAnular) {
    const filas = ingreso.procedimientos.map((p) => h("tr", { class: p.anulado ? "anulada" : "" },
      h("td", { class: "fecha" }, fechaHora(p.fecha_hora)),
      h("td", { class: "num-izq" }, p.codigo),
      h("td", {}, h("b", { class: p.anulado ? "tachada" : "" }, p.nombre),
        p.observaciones ? h("div", { class: "suave pequeno" }, p.observaciones) : null,
        p.anulado ? h("div", { class: "pequeno", style: "color:var(--cancelada)" }, `Anulado: ${p.motivo_anulacion}`) : null),
      h("td", { class: "num" }, p.cantidad), h("td", { class: "num" }, pesos(p.valor_unitario)),
      h("td", { class: "num" }, p.anulado ? "—" : pesos(p.subtotal)),
      h("td", {}, p.anulado ? h("span", { class: "sello anulada" }, "Anulado")
        : p.factura_numero ? h("span", { class: "sello pagada" }, p.factura_numero) : h("span", { class: "sello emitida" }, "Pendiente")),
      puedeAnular ? h("td", {}, !p.anulado && !p.factura_numero
        ? h("button", { class: "btn btn-pequeno btn-peligro", type: "button", onclick: () => anular(ingreso, p) }, "Anular") : null) : null));

    return h("section", { class: "panel" },
      h("h2", {}, "Procedimientos y cuenta"),
      ingreso.procedimientos.length
        ? h("div", { class: "tabla-contenedor" }, h("table", { class: "cuenta" },
          h("thead", {}, h("tr", {}, ["Fecha", "Código", "Procedimiento", "Cant.", "Valor unit.", "Subtotal", "Facturación", puedeAnular ? "" : null].filter((t) => t !== null).map((t, i) => h("th", { class: i >= 3 && i <= 5 ? "num" : "" }, t)))),
          h("tbody", {}, filas)))
        : vacio(esMedico ? "Aún no se registran procedimientos. Use «Registrar procedimiento»." : "El médico aún no ha registrado procedimientos."),
      h("div", { class: "totales" },
        h("div", {}, h("small", {}, "Total de la cuenta"), h("b", { class: "num" }, pesos(ingreso.total))),
        h("div", {}, h("small", {}, "Pendiente por facturar"), h("b", { class: "num" }, pesos(ingreso.pendiente_facturar)))));
  }

  function panelFacturas(facturas) {
    return h("section", { class: "panel" },
      h("h2", {}, "Facturas de este ingreso"),
      facturas.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Factura", "Fecha", "Total", "Estado", ""].map((t, i) => h("th", { class: i === 2 ? "num" : "" }, t)))),
          h("tbody", {}, facturas.map((f) => h("tr", {},
            h("td", { class: "num-izq" }, h("b", {}, f.numero)), h("td", { class: "fecha" }, fechaHora(f.fecha)),
            h("td", { class: "num" }, pesos(f.total)), h("td", {}, sello(f.estado)),
            h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirFactura(f, { puedeOperar: true, alCambiar: pintar }) }, "Ver / cobrar")))))))
        : vacio("Todavía no se ha facturado nada de este ingreso."));
  }

  // ---- acciones del médico

  async function registrar(ingreso) {
    let catalogo;
    try {
      catalogo = await api.get("/api/procedimientos");
    } catch (error) {
      aviso(error.message, "error");
      return;
    }
    abrirDialogo({
      titulo: "Registrar procedimiento",
      ancho: true,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const lista = seleccion("procedimiento_id", catalogo.map((p) => [p.id, `${p.codigo} · ${p.nombre}`]), catalogo[0]?.id);
        const cantidad = entrada("cantidad", { tipo: "number", valor: 1, min: 1, max: 99, requerido: true });
        const subtotal = h("b", { class: "num" });
        const actualizar = () => {
          const p = catalogo.find((x) => x.id === Number(lista.value));
          subtotal.textContent = p ? `${pesos(p.tarifa)} × ${Number(cantidad.value) || 0} = ${pesos(p.tarifa * (Number(cantidad.value) || 0))}` : "";
        };
        lista.addEventListener("change", actualizar);
        cantidad.addEventListener("input", actualizar);
        actualizar();
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Registrar en la historia clínica");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            guardar.disabled = true;
            const datos = datosDe(form);
            try {
              await api.post(`/api/ingresos/${ingreso.id}/procedimientos`, {
                procedimiento_id: Number(datos.procedimiento_id), cantidad: Number(datos.cantidad), observaciones: datos.observaciones,
              });
              cerrar();
              aviso("Procedimiento registrado y cargado a la cuenta.");
              pintar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              guardar.disabled = false;
            }
          },
        }, mensaje,
          h("div", { class: "rejilla-campos" }, campo("Procedimiento", lista), campo("Cantidad", cantidad)),
          h("p", { class: "valor-previo" }, "Valor: ", subtotal),
          campo("Observaciones clínicas", areaTexto("observaciones", "", { rows: 3, maxlength: 2000 }), "Solo las ve el personal médico."),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  function anular(ingreso, p) {
    abrirDialogo({
      titulo: "Anular procedimiento",
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const boton = h("button", { class: "btn btn-peligro", type: "submit" }, "Anular procedimiento");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            boton.disabled = true;
            try {
              await api.post(`/api/ingresos/${ingreso.id}/procedimientos/${p.id}/anular`, { motivo: form.elements.motivo.value.trim() });
              cerrar();
              aviso("Procedimiento anulado; ya no se cobra.");
              pintar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              boton.disabled = false;
            }
          },
        }, mensaje,
          h("p", {}, `${p.nombre} (${p.cantidad}) seguirá visible en la historia, marcado como anulado.`),
          campo("Motivo", areaTexto("motivo", "", { rows: 2, required: true, maxlength: 300 })),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
        cuerpo.append(form);
      },
    });
  }

  function egreso(ingreso) {
    abrirDialogo({
      titulo: "Dar egreso al paciente",
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Dar egreso");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            boton.disabled = true;
            try {
              await api.post(`/api/ingresos/${ingreso.id}/egreso`, { resumen: form.elements.resumen.value.trim() });
              cerrar();
              aviso("Egreso registrado.");
              pintar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              boton.disabled = false;
            }
          },
        }, mensaje,
          h("p", {}, "Al dar el egreso ya no se podrán registrar más procedimientos. Recepción podrá facturar lo pendiente."),
          campo("Resumen y conducta al egreso", areaTexto("resumen", "", { rows: 4, maxlength: 3000 })),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
        cuerpo.append(form);
      },
    });
  }

  // ---- acciones de recepción

  function facturar(ingreso, pendientes) {
    abrirDialogo({
      titulo: "Generar factura",
      ancho: true,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const total = h("b", { class: "num" });
        const casillas = pendientes.map((p) => {
          const c = h("input", { type: "checkbox", checked: true, value: p.id, "aria-label": p.nombre });
          c.addEventListener("change", actualizar);
          return c;
        });
        function actualizar() {
          const suma = pendientes.reduce((t, p, i) => t + (casillas[i].checked ? p.subtotal : 0), 0);
          total.textContent = pesos(suma);
          boton.disabled = !casillas.some((c) => c.checked);
        }
        const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Generar factura");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            boton.disabled = true;
            const ids = casillas.filter((c) => c.checked).map((c) => Number(c.value));
            try {
              const factura = await api.post("/api/facturas", { ingreso_id: ingreso.id, procedimiento_ids: ids });
              cerrar();
              aviso(`Factura ${factura.numero} generada.`);
              await pintar();
              abrirFactura(factura, { puedeOperar: true, alCambiar: pintar });
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              boton.disabled = false;
            }
          },
        }, mensaje,
          h("p", {}, "Elija los procedimientos que va a incluir. Los que deje sin marcar quedan pendientes para otra factura."),
          h("div", { class: "tabla-contenedor" }, h("table", { class: "cuenta" },
            h("thead", {}, h("tr", {}, [h("th", {}, h("span", { class: "solo-lector" }, "Incluir")), h("th", {}, "Procedimiento"), h("th", { class: "num" }, "Cant."), h("th", { class: "num" }, "Subtotal")])),
            h("tbody", {}, pendientes.map((p, i) => h("tr", {}, h("td", {}, casillas[i]), h("td", {}, h("b", {}, p.nombre)), h("td", { class: "num" }, p.cantidad), h("td", { class: "num" }, pesos(p.subtotal))))))),
          h("p", { class: "valor-previo" }, "Total de la factura: ", total),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), boton));
        cuerpo.append(form);
        actualizar();
      },
    });
  }
}
