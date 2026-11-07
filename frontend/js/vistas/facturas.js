import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, areaTexto, aviso, campo, CONCEPTOS_GLOSA, datosDe, entrada, fechaHora, h, METODOS_PAGO, pesos, seleccion, sello,
} from "../ui.js";
import { vacio } from "./pacientes.js";
import { abrirDocumento, bajarXml } from "./electronica.js";

// Detalle de una factura en un diálogo.
// `puedeOperar` (recepción) habilita cobrar al paciente y anular; `puedeCartera` (recepción o
// administrador) habilita la gestión frente al pagador: radicar, abonos y glosas.
export function abrirFactura(factura, { puedeOperar = false, puedeCartera = puedeOperar, alCambiar = () => {} } = {}) {
  abrirDialogo({
    titulo: `Factura ${factura.numero}`,
    ancho: true,
    construir: (cuerpo, cerrar) => pintar(cuerpo, cerrar, factura),
  });

  function pintar(cuerpo, cerrar, f) {
    const mensaje = h("div");
    const dato = (t, v) => h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
    const acciones = h("div", { class: "acciones no-imprimir" });
    const hayPagador = f.valor_pagador > 0 && f.estado !== "ANULADA";
    const ejecutar = (peticion, textoOk) => async (boton) => {
      boton.disabled = true;
      try {
        const nueva = await peticion();
        aviso(textoOk);
        alCambiar(nueva);
        pintar(cuerpo, cerrar, nueva);
      } catch (error) {
        mensaje.replaceChildren(alerta(error));
        boton.disabled = false;
      }
    };
    const refrescar = (nueva) => {
      alCambiar(nueva);
      pintar(cuerpo, cerrar, nueva);
    };

    if (puedeOperar && f.estado === "EMITIDA") {
      if (f.saldo_paciente > 0) {
        const metodo = seleccion("metodo_pago", METODOS_PAGO.filter(([v]) => v !== "EPS"), "EFECTIVO");
        const pagar = h("button", { class: "btn btn-primario", type: "button" }, `Cobrar al paciente ${pesos(f.saldo_paciente)}`);
        pagar.addEventListener("click", () => ejecutar(() => api.post(`/api/facturas/${f.id}/pagar`, { metodo_pago: metodo.value }), "Pago registrado.")(pagar));
        anexar(acciones, [h("div", { class: "pago" }, campo("Forma de pago", metodo), pagar)]);
      }
      if (!f.pagos.length && !f.fecha_radicacion) {
        anexar(acciones, [h("button", { class: "btn btn-peligro", type: "button", onclick: () => pedirAnulacion(f, cuerpo, cerrar) }, "Anular factura")]);
      }
    }
    anexar(acciones, [h("button", { class: "btn", type: "button", onclick: () => window.print() }, "Imprimir")]);

    cuerpo.replaceChildren();
    anexar(cuerpo, [
      mensaje,
      h("dl", { class: "ficha" },
        dato("Paciente", f.paciente_nombre), dato("Documento", f.paciente_documento),
        dato("Fecha de emisión", f.fecha ? fechaHora(f.fecha) : ""), dato("Emitida por", f.emitida_por),
        dato("Pagador", f.pagador_nombre), dato("Convenio", f.convenio_nombre),
        h("div", {}, h("dt", {}, "Estado"), h("dd", {}, sello(f.estado)))),
      f.estado === "ANULADA" ? h("div", { class: "alerta" }, h("b", {}, "Factura anulada. "), f.motivo_anulacion) : null,
      h("div", { class: "tabla-contenedor" }, h("table", { class: "cuenta" },
        h("thead", {}, h("tr", {}, ["Código", "Procedimiento", "Cant.", "Valor unitario", "Subtotal"].map((t, i) => h("th", { class: i > 1 ? "num" : "" }, t)))),
        h("tbody", {}, f.lineas.map((l) => h("tr", {},
          h("td", { class: "num-izq" }, l.codigo), h("td", {}, l.descripcion),
          h("td", { class: "num" }, l.cantidad), h("td", { class: "num" }, pesos(l.valor_unitario)), h("td", { class: "num" }, pesos(l.subtotal))))),
        h("tfoot", {}, h("tr", {}, h("th", { colspan: 4, class: "num" }, "Total"), h("th", { class: "num total" }, pesos(f.total)))))),
      f.estado === "ANULADA" && !f.factura_electronica ? null : seccionElectronica(f, { puedeCartera, mensaje, ejecutar, refrescar }),
      f.estado === "ANULADA" ? null : desglose(f, hayPagador),
      hayPagador ? seccionCartera(f, { puedeCartera, mensaje, ejecutar, refrescar }) : null,
      f.pagos.length ? historialPagos(f) : null,
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
          h("p", {}, "Los procedimientos volverán a quedar pendientes y podrán facturarse de nuevo. Una factura con pagos recibidos o ya radicada al pagador no se puede anular."),
          f.factura_electronica?.estado === "ACEPTADO"
            ? h("p", { class: "nota-dian" }, `Esta factura ya tiene la factura electrónica ${f.factura_electronica.numero} aceptada: al anularla se emite automáticamente una nota crédito por ${pesos(f.factura_electronica.valor)}.`)
            : null,
          campo("Motivo de la anulación", areaTexto("motivo", "", { rows: 2, required: true, maxlength: 300 })),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
        cuerpo.append(form);
      },
    });
  }
}


function fila(titulo, valor, fuerte = false) {
  return h("div", { class: fuerte ? "fila-saldo fuerte" : "fila-saldo" }, h("span", {}, titulo), h("b", { class: "num" }, valor));
}

// A cargo del paciente y a cargo del pagador, con lo ya pagado y lo que queda por cobrar.
function desglose(f, hayPagador) {
  const bloquePaciente = h("div", { class: "bloque-saldo" },
    h("h3", {}, "A cargo del paciente"),
    fila("Valor", pesos(f.valor_paciente)), fila("Pagado", pesos(f.pagado_paciente)), fila("Saldo", pesos(f.saldo_paciente), true));
  if (!hayPagador) return h("div", { class: "desglose" }, bloquePaciente);
  return h("div", { class: "desglose" }, bloquePaciente,
    h("div", { class: "bloque-saldo" },
      h("h3", {}, `A cargo de ${f.pagador_nombre}`),
      fila("Valor", pesos(f.valor_pagador)), fila("Abonos recibidos", pesos(f.pagado_pagador)),
      f.glosado_aceptado ? fila("Glosa aceptada", pesos(f.glosado_aceptado)) : null,
      f.glosa_en_disputa ? fila("Glosa en disputa", pesos(f.glosa_en_disputa)) : null,
      fila("Saldo", pesos(f.saldo_pagador), true)));
}

function historialPagos(f) {
  return h("section", { class: "subseccion" }, h("h3", {}, "Pagos recibidos"),
    h("div", { class: "tabla-contenedor" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Recibo", "Fecha", "Quién pagó", "Forma", "Referencia", "Valor"].map((t, i) => h("th", { class: i === 5 ? "num" : "" }, t)))),
      h("tbody", {}, f.pagos.map((p) => h("tr", {},
        h("td", { class: "num-izq" }, h("b", {}, p.recibo_numero || "—")), h("td", { class: "fecha" }, fechaHora(p.fecha)), h("td", {}, p.origen === "PAGADOR" ? f.pagador_nombre : "Paciente"),
        h("td", {}, METODOS_PAGO.find(([v]) => v === p.metodo)?.[1] || p.metodo), h("td", {}, p.referencia || "—"),
        h("td", { class: "num" }, pesos(p.valor))))))));
}

// Factura electrónica DIAN de la factura y sus notas crédito.
function seccionElectronica(f, { puedeCartera, mensaje, ejecutar, refrescar }) {
  const fe = f.factura_electronica;
  const partes = [h("h3", {}, "Factura electrónica DIAN")];
  const abrir = (doc) => h("button", { class: "btn btn-pequeno", type: "button", onclick: () => detalle(doc) }, "Ver detalle");
  const detalle = async (doc) => {
    try {
      abrirDocumento(await api.get(`/api/electronica/documentos/${doc.id}`), { puedeOperar: puedeCartera, alCambiar: () => refrescarDesdeServidor() });
    } catch (error) {
      mensaje.replaceChildren(alerta(error));
    }
  };
  const refrescarDesdeServidor = async () => refrescar(await api.get(`/api/facturas/${f.id}`));

  if (!fe) {
    if (f.estado === "ANULADA") return null;
    partes.push(h("p", { class: "suave" }, f.dian_obligatoria
      ? `Aún no se ha emitido. Se factura a ${f.valor_pagador > 0 ? f.pagador_nombre : "el paciente"} por ${pesos(f.valor_pagador > 0 ? f.valor_pagador : f.valor_paciente)}; es indispensable para radicar al pagador.`
      : "Aún no se ha emitido."));
    if (puedeCartera) {
      const boton = h("button", { class: "btn btn-primario", type: "button" }, "Emitir factura electrónica");
      boton.addEventListener("click", () => ejecutar(() => api.post(`/api/electronica/facturas/${f.id}/emitir`).then(() => api.get(`/api/facturas/${f.id}`)), "Documento enviado al proveedor.")(boton));
      partes.push(h("div", { class: "acciones" }, boton));
    }
    return h("section", { class: "subseccion" }, partes);
  }

  partes.push(
    h("div", { class: "fila-dian" }, h("b", { class: "num" }, fe.numero), sello(fe.estado), h("span", { class: "suave" }, `a ${fe.adquirente_nombre} · ${pesos(fe.valor)}`)),
    h("p", { class: fe.estado === "RECHAZADO" ? "alerta" : "suave pequeno" }, fe.mensaje_respuesta),
    h("code", { class: "cufe" }, fe.cufe),
    h("div", { class: "acciones no-imprimir", style: "margin-top:.4rem" }, abrir(fe),
      h("button", { class: "btn btn-pequeno", type: "button", onclick: () => bajarXml(fe) }, "Descargar XML")));

  if (f.notas_credito.length) {
    partes.push(h("h4", {}, "Notas crédito"), h("ul", { class: "glosas" }, f.notas_credito.map((n) => h("li", { class: "glosa" },
      h("div", { class: "glosa-cabecera" }, h("b", { class: "num" }, n.numero), " · ", h("b", { class: "num" }, pesos(n.valor)), sello(n.estado)),
      h("p", { class: "suave pequeno" }, n.motivo), h("div", { class: "acciones", style: "margin-top:.3rem" }, abrir(n))))));
  }
  const pendientes = fe.estado === "ACEPTADO" && puedeCartera
    ? f.glosas.filter((g) => g.estado === "ACEPTADA" && !f.notas_credito.some((n) => n.glosa_id === g.id && n.estado !== "RECHAZADO"))
    : [];
  for (const g of pendientes) {
    const boton = h("button", { class: "btn btn-pequeno", type: "button" }, `Emitir nota crédito por la glosa de ${pesos(g.valor)}`);
    boton.addEventListener("click", () => ejecutar(
      () => api.post(`/api/electronica/facturas/${f.id}/notas-credito`, { concepto: "GLOSA", glosa_id: g.id }).then(() => api.get(`/api/facturas/${f.id}`)),
      "Nota crédito emitida.")(boton));
    partes.push(h("div", { class: "acciones", style: "margin-top:.3rem" }, boton));
  }
  return h("section", { class: "subseccion" }, partes);
}

// Gestión frente al pagador: radicación, abonos y glosas.
function seccionCartera(f, { puedeCartera, mensaje, ejecutar, refrescar }) {
  const radicada = Boolean(f.fecha_radicacion);
  const partes = [h("h3", {}, "Cartera con el pagador")];

  if (!radicada) {
    const numero = entrada("numero_radicacion", { placeholder: "Se genera si lo deja vacío", maxlength: 40 });
    const boton = h("button", { class: "btn btn-primario", type: "button" }, "Radicar al pagador");
    boton.addEventListener("click", () => ejecutar(
      () => api.post(`/api/facturas/${f.id}/radicar`, { numero_radicacion: numero.value.trim() }), "Factura radicada.")(boton));
    partes.push(h("p", { class: "suave" }, "Aún no se ha radicado. El pagador solo puede abonar o glosar una factura radicada.",
      f.dian_obligatoria && f.factura_electronica?.estado !== "ACEPTADO" ? " Antes debe tener su factura electrónica aceptada." : ""),
      puedeCartera ? h("div", { class: "pago" }, campo("Número de radicación", numero), boton) : null);
    return h("section", { class: "subseccion" }, partes);
  }

  partes.push(h("p", {}, "Radicada el ", h("b", {}, fechaHora(f.fecha_radicacion)), " con el número ", h("b", { class: "num" }, f.numero_radicacion),
    ` (hace ${f.dias_radicada} ${f.dias_radicada === 1 ? "día" : "días"}).`));

  const libre = f.saldo_pagador - f.glosa_en_disputa;
  if (puedeCartera && f.estado === "EMITIDA" && libre > 0) {
    const valor = entrada("valor", { tipo: "number", valor: libre, min: 1, max: libre, step: 1, inputmode: "numeric", requerido: true });
    const metodo = seleccion("metodo_pago", METODOS_PAGO.filter(([v]) => v !== "EFECTIVO"), "TRANSFERENCIA");
    const referencia = entrada("referencia", { maxlength: 60, placeholder: "Comprobante o transferencia" });
    const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Registrar abono");
    const form = h("form", {
      class: "pago",
      onsubmit: (e) => {
        e.preventDefault();
        ejecutar(() => api.post(`/api/facturas/${f.id}/pagos-pagador`, {
          valor: Number(valor.value), metodo_pago: metodo.value, referencia: referencia.value.trim(),
        }), "Abono registrado.")(boton);
      },
    }, campo("Valor del abono", valor), campo("Forma", metodo), campo("Referencia", referencia), boton);
    partes.push(h("h4", {}, "Abono del pagador"), form,
      f.glosa_en_disputa ? h("p", { class: "suave pequeno" }, `Se puede abonar hasta ${pesos(libre)}; ${pesos(f.glosa_en_disputa)} están en disputa por glosas abiertas.`) : null);
  }

  partes.push(h("h4", {}, "Glosas"));
  partes.push(f.glosas.length
    ? h("ul", { class: "glosas" }, f.glosas.map((g) => tarjetaGlosa(f, g, { puedeCartera, ejecutar, refrescar })))
    : h("p", { class: "suave" }, "Sin glosas."));
  if (puedeCartera && f.estado === "EMITIDA" && libre > 0) {
    partes.push(h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formGlosa(f, refrescar) }, "Registrar glosa"));
  }
  return h("section", { class: "subseccion" }, partes);
}

function tarjetaGlosa(f, g, { puedeCartera, ejecutar, refrescar }) {
  const abierta = g.estado === "ABIERTA";
  const respondida = g.estado === "RESPONDIDA";
  const botones = [];
  if (puedeCartera && abierta) {
    botones.push(h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formRespuesta(f, g, refrescar) }, "Responder"));
  }
  if (puedeCartera && (abierta || respondida)) {
    botones.push(
      h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formResolucion(f, g, false, refrescar) }, "Pagador la levantó"),
      h("button", { class: "btn btn-pequeno btn-peligro", type: "button", onclick: () => formResolucion(f, g, true, refrescar) }, "Aceptar glosa"));
  }
  return h("li", { class: "glosa" },
    h("div", { class: "glosa-cabecera" },
      h("b", {}, CONCEPTOS_GLOSA[g.concepto] || g.concepto), " · ", h("b", { class: "num" }, pesos(g.valor)), sello(g.estado)),
    h("p", {}, g.motivo),
    g.respuesta ? h("p", { class: "suave pequeno" }, h("b", {}, "Respuesta de la IPS: "), g.respuesta) : null,
    g.nota_resolucion ? h("p", { class: "suave pequeno" }, h("b", {}, "Resolución: "), g.nota_resolucion) : null,
    botones.length ? h("div", { class: "acciones", style: "margin-top:.3rem" }, botones) : null);
}

function dialogoSimple(titulo, f, contenido, enviar, textoBoton, peligro = false) {
  abrirDialogo({
    titulo,
    construir: (cuerpo, cerrar) => {
      const mensaje = h("div");
      const boton = h("button", { class: `btn ${peligro ? "btn-peligro" : "btn-primario"}`, type: "submit" }, textoBoton);
      const partes = contenido();
      const form = h("form", {
        onsubmit: async (e) => {
          e.preventDefault();
          boton.disabled = true;
          try {
            await enviar(form, cerrar);
          } catch (error) {
            mensaje.replaceChildren(alerta(error));
            boton.disabled = false;
          }
        },
      }, mensaje, partes,
        h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
      cuerpo.append(form);
    },
  });
}

function formGlosa(f, refrescar) {
  const libre = f.saldo_pagador - f.glosa_en_disputa;
  dialogoSimple(`Registrar glosa en ${f.numero}`, f, () => [
    h("div", { class: "rejilla-campos" },
      campo("Concepto", seleccion("concepto", Object.entries(CONCEPTOS_GLOSA), "FACTURACION")),
      campo("Valor glosado (pesos)", entrada("valor", { tipo: "number", requerido: true, min: 1, max: libre, step: 1, inputmode: "numeric" }), `Máximo ${pesos(libre)}.`)),
    campo("Motivo que da el pagador", areaTexto("motivo", "", { rows: 3, required: true, maxlength: 500 })),
  ], async (form, cerrar) => {
    const d = datosDe(form);
    const nueva = await api.post(`/api/facturas/${f.id}/glosas`, { concepto: d.concepto, motivo: d.motivo, valor: Number(d.valor) });
    cerrar();
    aviso("Glosa registrada.");
    refrescar(nueva);
  }, "Registrar glosa");
}

function formRespuesta(f, g, refrescar) {
  dialogoSimple("Responder la glosa", f, () => [
    h("p", {}, `${CONCEPTOS_GLOSA[g.concepto]} · ${pesos(g.valor)}: ${g.motivo}`),
    campo("Respuesta de la IPS", areaTexto("respuesta", "", { rows: 4, required: true, maxlength: 1000 }), "Argumentos y soportes que se envían al pagador."),
  ], async (form, cerrar) => {
    const nueva = await api.post(`/api/facturas/${f.id}/glosas/${g.id}/responder`, { respuesta: form.elements.respuesta.value.trim() });
    cerrar();
    aviso("Respuesta registrada.");
    refrescar(nueva);
  }, "Guardar respuesta");
}

function formResolucion(f, g, aceptada, refrescar) {
  dialogoSimple(aceptada ? "Aceptar la glosa" : "El pagador levantó la glosa", f, () => [
    h("p", {}, aceptada
      ? `La IPS acepta que no cobrará ${pesos(g.valor)}. Ese valor sale del saldo del pagador.`
      : `El pagador reconoce los ${pesos(g.valor)} y vuelven a quedar por cobrar.`),
    campo("Nota (opcional)", areaTexto("nota", "", { rows: 2, maxlength: 500 })),
  ], async (form, cerrar) => {
    const nueva = await api.post(`/api/facturas/${f.id}/glosas/${g.id}/resolver`, { aceptada, nota: form.elements.nota.value.trim() });
    cerrar();
    aviso(aceptada ? "Glosa aceptada." : "Glosa levantada.");
    refrescar(nueva);
  }, aceptada ? "Aceptar glosa" : "Confirmar", aceptada);
}

// Pantalla de facturación (recepción gestiona; el administrador consulta y puede gestionar cartera).
export async function montarFacturas(raiz, { usuario }) {
  const puedeOperar = usuario.rol === "RECEPCION";
  const filtro = seleccion("estado", [["", "Todas"], ["EMITIDA", "Por cobrar"], ["PAGADA", "Pagadas"], ["ANULADA", "Anuladas"]], "");
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando facturas…"));
    try {
      const todas = await api.get("/api/facturas");
      const vigentes = todas.filter((f) => f.estado !== "ANULADA");
      const suma = (campoValor) => vigentes.reduce((t, f) => t + f[campoValor], 0);
      const lista = filtro.value ? todas.filter((f) => f.estado === filtro.value) : todas;
      zona.replaceChildren(
        h("div", { class: "resumen-cifras" },
          cifra("Facturado", pesos(vigentes.reduce((t, f) => t + f.total, 0)), ""),
          cifra("Por cobrar al paciente", pesos(suma("saldo_paciente")), "pendiente"),
          cifra("Por cobrar a pagadores", pesos(suma("saldo_pagador")), "pendiente"),
          cifra("Facturas anuladas", String(todas.length - vigentes.length), "")),
        lista.length
          ? h("div", { class: "tabla-contenedor" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Factura", "Fecha", "Paciente", "Pagador", "Total", "Saldo", "Estado", ""].map((t, i) => h("th", { class: i === 4 || i === 5 ? "num" : "" }, t)))),
            h("tbody", {}, lista.map((f) => h("tr", {},
              h("td", { class: "num-izq" }, h("b", {}, f.numero)), h("td", { class: "fecha" }, fechaHora(f.fecha)),
              h("td", {}, h("b", {}, f.paciente_nombre), h("div", { class: "suave pequeno num" }, f.paciente_documento)),
              h("td", {}, f.pagador_nombre || "—"),
              h("td", { class: "num" }, pesos(f.total)), h("td", { class: "num" }, f.estado === "ANULADA" ? "—" : pesos(f.saldo)), h("td", {}, sello(f.estado)),
              h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirFactura(f, { puedeOperar, puedeCartera: true, alCambiar: cargar }) }, "Ver")))))))
          : vacio(todas.length ? "No hay facturas con ese estado." : "Todavía no se ha facturado nada. Las facturas se generan desde la cuenta de cada ingreso."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  filtro.addEventListener("change", cargar);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Facturación"),
        h("p", {}, puedeOperar ? "Facturas generadas desde la cuenta de cada ingreso: cobre al paciente, radique al pagador o anule las que tengan errores." : "Consulta de facturas, saldos por cobrar y gestión de cartera."))),
    h("section", { class: "panel" }, h("div", { class: "barra" }, campo("Mostrar", filtro)), zona));
  await cargar();
}

function cifra(titulo, valor, tono) {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}
