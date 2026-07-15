// Gerador de Ata (.docx) — OOXML montado à mão. Usável em Node e no navegador.
// Exporta: buildDocxParts(data, logoB64) -> { "path": {text} | {b64} }
//
// ATENÇÃO: as cores abaixo são as do DOCUMENTO Word (padrão oficial da ata da
// Stewart), não as da interface do portal. Mantido em sincronia com o gerador
// do Claude (gerar_ata_docx.py): mudança de layout deve ser aplicada nos dois.
(function (root) {
  const RED = "BE2F26", GRAFITE = "2B2B2B", CINZA = "6E6E6E",
        BORDER = "D0D0D0", FILL = "F2F2F2", WHITE = "FFFFFF", FONT = "Arial";
  const tw = cm => Math.round(cm * 566.93);
  const esc = s => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  const statusColor = s => ({
    "pendente": RED, "em andamento": "C77700", "concluído": "2E7D32", "concluido": "2E7D32"
  })[(s || "").trim().toLowerCase()] || CINZA;

  // run de texto
  function run(text, o = {}) {
    const sz = (o.sz || 10) * 2;
    const rpr = `<w:rPr>` +
      `<w:rFonts w:ascii="${FONT}" w:hAnsi="${FONT}" w:cs="${FONT}"/>` +
      (o.b ? `<w:b/>` : ``) + (o.i ? `<w:i/>` : ``) +
      `<w:color w:val="${o.color || GRAFITE}"/>` +
      `<w:sz w:val="${sz}"/><w:szCs w:val="${sz}"/></w:rPr>`;
    return `<w:r>${rpr}<w:t xml:space="preserve">${esc(text)}</w:t></w:r>`;
  }

  // parágrafo
  function para(runsXml, o = {}) {
    let p = ``;
    if (o.pBdr) {
      const edges = o.pBdr === "box" ? ["top", "left", "bottom", "right"] : ["bottom"];
      const col = o.borderColor || BORDER, szb = o.borderSz || 4, sp = o.pBdr === "box" ? 6 : 4;
      p += `<w:pBdr>` + edges.map(e =>
        `<w:${e} w:val="single" w:sz="${szb}" w:space="${sp}" w:color="${col}"/>`).join("") + `</w:pBdr>`;
    }
    // Só escreve o espaçamento pedido; sem ele o parágrafo herda o padrão do
    // documento (entrelinha 1,15 / 200 depois), como no modelo oficial.
    let sp = ``;
    if (o.before != null) sp += ` w:before="${o.before}"`;
    if (o.after != null) sp += ` w:after="${o.after}"`;
    if (sp) p += `<w:spacing${sp}/>`;
    if (o.indent || o.indentRight) {
      p += `<w:ind` + (o.indent ? ` w:left="${tw(o.indent)}"` : ``) +
        (o.indentRight ? ` w:right="${tw(o.indentRight)}"` : ``) + `/>`;
    }
    if (o.jc) p += `<w:jc w:val="${o.jc}"/>`;
    return `<w:p><w:pPr>${p}</w:pPr>${runsXml}</w:p>`;
  }

  function cell(runsOrParas, o = {}) {
    const tcPr = `<w:tcPr>` +
      `<w:tcW w:w="${tw(o.w)}" w:type="dxa"/>` +
      (o.fill ? `<w:shd w:val="clear" w:color="auto" w:fill="${o.fill}"/>` : ``) +
      `<w:tcMar><w:top w:w="${o.mt != null ? o.mt : 60}" w:type="dxa"/>` +
      `<w:start w:w="${o.ml != null ? o.ml : 120}" w:type="dxa"/>` +
      `<w:bottom w:w="${o.mb != null ? o.mb : 60}" w:type="dxa"/>` +
      `<w:end w:w="${o.mr != null ? o.mr : 120}" w:type="dxa"/></w:tcMar>` +
      `<w:vAlign w:val="${o.valign || "center"}"/></w:tcPr>`;
    const body = Array.isArray(runsOrParas) ? runsOrParas.join("") : runsOrParas;
    return `<w:tc>${tcPr}${body}</w:tc>`;
  }

  function table(rowsXml, widths, o = {}) {
    const total = widths.reduce((a, b) => a + b, 0);
    const borders = o.noBorders
      ? `<w:tblBorders>${["top", "left", "bottom", "right", "insideH", "insideV"]
          .map(e => `<w:${e} w:val="nil"/>`).join("")}</w:tblBorders>`
      : `<w:tblBorders>${["top", "left", "bottom", "right", "insideH", "insideV"]
          .map(e => `<w:${e} w:val="single" w:sz="4" w:space="0" w:color="${BORDER}"/>`).join("")}</w:tblBorders>`;
    const grid = `<w:tblGrid>${widths.map(w => `<w:gridCol w:w="${tw(w)}"/>`).join("")}</w:tblGrid>`;
    return `<w:tbl><w:tblPr>` +
      `<w:tblW w:w="${tw(total)}" w:type="dxa"/><w:jc w:val="center"/>` +
      borders + `<w:tblLayout w:type="fixed"/></w:tblPr>${grid}${rowsXml}</w:tbl>`;
  }
  const row = cellsXml => `<w:tr>${cellsXml}</w:tr>`;

  function sectionTitle(txt) {
    return para(run(txt, { b: true, sz: 11, color: RED }),
      { pBdr: "bottom", borderColor: BORDER, borderSz: 6, before: 120, after: 80 });
  }

  function logoDrawing() {
    return `<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">` +
      `<wp:extent cx="1548000" cy="339640"/><wp:effectExtent l="0" t="0" r="0" b="0"/>` +
      `<wp:docPr id="1" name="logo"/><wp:cNvGraphicFramePr/>` +
      `<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">` +
      `<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
      `<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
      `<pic:nvPicPr><pic:cNvPr id="1" name="logo"/><pic:cNvPicPr/></pic:nvPicPr>` +
      `<pic:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>` +
      `<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1548000" cy="339640"/></a:xfrm>` +
      `<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>` +
      `</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>`;
  }

  function buildBody(d) {
    let b = "";
    // título
    b += para(run("ATA DE REUNIÃO", { b: true, sz: 18, color: GRAFITE }));
    const obra = d.obra || "[a confirmar]";
    const num = String(d.numero || "00").padStart(2, "0");
    b += para(run("Obra " + obra, { b: true, sz: 10, color: RED }) +
      run("      Ata nº " + num + "      Revisão 00", { sz: 10, color: CINZA }),
      { before: 40, after: 200 });

    // identificação
    const idw = [3.6, 13.4];
    const idrows = [["Cliente", d.cliente], ["Endereço", d.endereco], ["Data", d.data], ["Local", d.local]];
    let idXml = "";
    for (const [k, v] of idrows) {
      idXml += row(
        cell(para(run(k, { b: true, sz: 9.5 })), { w: idw[0], fill: FILL }) +
        cell(para(run(v || "[a confirmar]", { sz: 9.5, color: v ? GRAFITE : CINZA })), { w: idw[1] }));
    }
    b += table(idXml, idw);
    b += para("", { after: 80 });

    // participantes
    b += sectionTitle("PARTICIPANTES");
    const pw = [9.5, 7.5];
    let pXml = row(
      cell(para(run("Nome", { b: true, sz: 9.5, color: WHITE })), { w: pw[0], fill: RED }) +
      cell(para(run("Empresa / Função", { b: true, sz: 9.5, color: WHITE })), { w: pw[1], fill: RED }));
    (d.participantes || []).forEach((p, i) => {
      const f = (i % 2 === 1) ? FILL : null;
      pXml += row(
        cell(para(run(p.nome || "", { sz: 9.5 })), { w: pw[0], fill: f }) +
        cell(para(run(p.empresa || "", { sz: 9.5, color: CINZA })), { w: pw[1], fill: f }));
    });
    b += table(pXml, pw);
    b += para("", { after: 80 });

    // pauta
    b += sectionTitle("PAUTA E DELIBERAÇÕES");
    (d.assuntos || []).forEach((a, i) => {
      const bw = [0.9, 16.1];
      const badge = row(
        cell(para(run(String(i + 1), { b: true, sz: 11, color: WHITE }), { jc: "center" }),
          { w: bw[0], fill: RED, mt: 40, mb: 40, ml: 40, mr: 40 }) +
        cell(para(run(a.titulo || "[a confirmar]", { b: true, sz: 11 })),
          { w: bw[1], mt: 40, mb: 40, ml: 160, mr: 40 }));
      b += table(badge, bw, { noBorders: true });
      b += para(run(a.descricao || "[a confirmar]", { sz: 10, color: a.descricao ? GRAFITE : CINZA }),
        { indent: 0.9, before: 60, after: 60 });
      b += para(
        run("Responsável: ", { b: true, sz: 8.5, color: CINZA }) +
        run(a.responsavel || "[a confirmar]", { sz: 8.5, color: CINZA }) +
        run("      Prazo: ", { b: true, sz: 8.5, color: CINZA }) +
        run(a.prazo || "[a confirmar]", { sz: 8.5, color: CINZA }),
        { indent: 0.9, after: 160 });
    });

    // plano de ação
    const acoes = (d.assuntos || []).filter(a => a.responsavel || a.prazo);
    if (acoes.length) {
      b += para("", { after: 40 });
      b += sectionTitle("PLANO DE AÇÃO");
      const aw = [0.9, 7.0, 3.6, 2.7, 2.8];
      const hd = ["#", "Ação", "Responsável", "Prazo", "Status"];
      let aXml = row(hd.map((t, j) =>
        cell(para(run(t, { b: true, sz: 9, color: WHITE }), { jc: j === 0 ? "center" : "left" }),
          { w: aw[j], fill: RED })).join(""));
      acoes.forEach((a, k) => {
        const f = (k % 2 === 1) ? FILL : null;
        const st = a.status || "Pendente";
        aXml += row(
          cell(para(run(String(k + 1), { sz: 9 }), { jc: "center" }), { w: aw[0], fill: f }) +
          cell(para(run(a.titulo || "", { sz: 9 })), { w: aw[1], fill: f }) +
          cell(para(run(a.responsavel || "[a confirmar]", { sz: 9, color: CINZA })), { w: aw[2], fill: f }) +
          cell(para(run(a.prazo || "[a confirmar]", { sz: 9, color: CINZA })), { w: aw[3], fill: f }) +
          cell(para(run(st, { b: true, sz: 9, color: statusColor(st) })), { w: aw[4], fill: f }));
      });
      b += table(aXml, aw);
    }

    // aprovação
    b += para("", { after: 40 });
    b += sectionTitle("APROVAÇÃO");
    const prazoAp = d.prazo_aprovacao || "2 (dois) dias úteis";
    b += para(run("Esta ata reflete os entendimentos e deliberações da reunião. Caso não haja " +
      "manifestação formal em contrário no prazo de " + prazoAp + ", a contar do seu recebimento, " +
      "o conteúdo será considerado integralmente aprovado pelas partes.",
      { i: true, sz: 9, color: GRAFITE }),
      { pBdr: "box", borderColor: BORDER, borderSz: 4, before: 40, after: 40,
        indent: 0.2, indentRight: 0.2 });

    // sectPr
    b += `<w:sectPr>` +
      `<w:headerReference w:type="default" r:id="rId4"/>` +
      `<w:footerReference w:type="default" r:id="rId5"/>` +
      `<w:pgSz w:w="11906" w:h="16838"/>` +
      `<w:pgMar w:top="1644" w:right="1134" w:bottom="1020" w:left="1134" ` +
      `w:header="567" w:footer="454" w:gutter="0"/></w:sectPr>`;
    return b;
  }

  function documentXml(d) {
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
      `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
      `xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">` +
      `<w:body>${buildBody(d)}</w:body></w:document>`;
  }

  function headerXml() {
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
      `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ` +
      `xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">` +
      `<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="18" w:space="4" w:color="${RED}"/></w:pBdr>` +
      `</w:pPr>${logoDrawing()}</w:p></w:hdr>`;
  }

  function footerXml() {
    const fw = [11, 6];
    const pageRun = `<w:r><w:fldChar w:fldCharType="begin"/></w:r>` +
      `<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>` +
      `<w:r><w:fldChar w:fldCharType="end"/></w:r>`;
    const numRun = `<w:r><w:fldChar w:fldCharType="begin"/></w:r>` +
      `<w:r><w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r>` +
      `<w:r><w:fldChar w:fldCharType="end"/></w:r>`;
    const right = `<w:p><w:pPr><w:jc w:val="right"/></w:pPr>` +
      run("Página ", { sz: 8, color: CINZA }) + pageRun + run(" de ", { sz: 8, color: CINZA }) + numRun + `</w:p>`;
    const left = `<w:p><w:pPr></w:pPr>` +
      run("STEWART ENGENHARIA", { b: true, sz: 7, color: CINZA }) +
      run("   •   Documento confidencial", { sz: 7, color: CINZA }) + `</w:p>`;
    const tbl = table(row(cell(left, { w: fw[0] }) + cell(right, { w: fw[1] })), fw, { noBorders: true });
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
      `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
      `${tbl}<w:p><w:pPr></w:pPr></w:p></w:ftr>`;
  }

  const stylesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:docDefaults><w:rPrDefault><w:rPr>` +
    `<w:rFonts w:ascii="${FONT}" w:hAnsi="${FONT}" w:cs="${FONT}"/>` +
    `<w:color w:val="${GRAFITE}"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:rPrDefault>` +
    `<w:pPrDefault><w:pPr><w:spacing w:after="200" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>` +
    `</w:docDefaults>` +
    `<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>`;

  const settingsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:zoom w:percent="100"/><w:defaultTabStop w:val="708"/>` +
    `<w:updateFields w:val="true"/></w:settings>`;

  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
    `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
    `<Default Extension="xml" ContentType="application/xml"/>` +
    `<Default Extension="png" ContentType="image/png"/>` +
    `<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>` +
    `<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>` +
    `<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>` +
    `<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>` +
    `<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>` +
    `</Types>`;

  const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>` +
    `</Relationships>`;

  const docRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    `<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
    `<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>` +
    `<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>` +
    `<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>` +
    `</Relationships>`;

  const headerRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
    `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/>` +
    `</Relationships>`;

  function buildDocxParts(d, logoB64) {
    return {
      "[Content_Types].xml": { text: contentTypes },
      "_rels/.rels": { text: rootRels },
      "word/document.xml": { text: documentXml(d) },
      "word/_rels/document.xml.rels": { text: docRels },
      "word/styles.xml": { text: stylesXml },
      "word/settings.xml": { text: settingsXml },
      "word/header1.xml": { text: headerXml() },
      "word/_rels/header1.xml.rels": { text: headerRels },
      "word/footer1.xml": { text: footerXml() },
      "word/media/logo.png": { b64: logoB64 },
    };
  }

  root.AtaDocx = { buildDocxParts };
})(typeof window !== "undefined" ? window : globalThis);
