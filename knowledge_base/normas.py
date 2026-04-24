"""Constantes normativas extraídas dos modelos oficiais MPBA (Jan/2026).

Cada constante é um dicionário de metadados que documenta:
  - fonte: documento oficial de origem
  - norma: dispositivo legal aplicável
  - descricao: descrição da regra
  - campos (quando aplicável): estrutura de campos do documento

Este módulo NÃO contém lógica de validação – apenas a base factual.
A lógica de validação está nos módulos rules/.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# NORMAS GERAIS – Dispensa de Licitação Não Eletrônica Sem Contrato
# ─────────────────────────────────────────────────────────────────────────────

NORMAS_GERAIS: dict = {
    "modalidade": "Dispensa de Licitação Não Eletrônica – Sem Contrato",
    "lei_federal": "Lei nº 14.133/2021",
    "lei_estadual": "Lei Estadual nº 14.634/2023",
    "ato_normativo_mpba": "Ato Normativo MPBA nº 048/2024",
    "artigos_aplicaveis": {
        "compras_servicos_comuns": "art. 75, inciso II (valor ≤ R$ 57.906,09)",
        "servicos_engenharia": "art. 75, inciso I (valor ≤ R$ 115.812,17)",
        "limite_paragrafo_1": "art. 75, §1º – limite anual por categoria",
        "aviso_previo": "art. 75, §3º – aviso prévio mínimo de 3 dias úteis",
    },
    "prazo_envio_dccl_dias_uteis": 10,
    # O processo deve ser enviado à DCCL com 10 du de antecedência
    # em relação à data pretendida para o início da execução/fornecimento.
    "fonte": "Ato Normativo MPBA nº 048/2024 + Lei 14.133/2021",
}

# ─────────────────────────────────────────────────────────────────────────────
# DFD – Documento de Formalização de Demanda
# Modelo oficial MPBA (extraído do template institucional)
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_DFD: dict = {
    "nome_documento": "DOCUMENTO DE FORMALIZAÇÃO DA DEMANDA",
    "abreviatura": "DFD",
    "posicao_no_processo": "primeiro_documento",
    "fonte": "Modelo DFD – MPBA",
    "campos_obrigatorios": [
        "Objeto da Futura Contratação",
        "Tecnologia da Informação e Comunicação (TIC) – SIM ou NÃO",
        "Unidade Solicitante",
        "Unidade Gestora do Recurso (formato: XX.XXX – Nome da Unidade)",
        "Origem Convênio – SIM ou NÃO (se SIM: nome concedente + número convênio)",
        "Vinculação ao PCA – SIM ou NÃO (se NÃO: justificativa + Despacho/Decisão SGA)",
        "Justificativa para escolha da forma não eletrônica",
        "Assinatura do Responsável pelo Preenchimento",
        "Ciência do Superior Imediato (assinatura ou despacho)",
    ],
    "campo_unidade_gestora_regex": r"^\d{2}\.\d{3}\s*[–\-]",
    # Exemplo: "40.101 – Assessoria de Contratações"
    "pca_nao_exige": [
        "justificativa_ausencia_pca",
        "despacho_decisao_sga",  # obrigatório após justificativa
    ],
    "forma_nao_eletronica": {
        "descricao": "Justificativa para escolha da forma não eletrônica de DL",
        "obrigatorio": True,
        "norma": "Art. 75, §3º, Lei 14.133/2021",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TR SERVIÇOS – Termo de Referência – Serviços (Jan/2026)
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_TR_SERVICOS: dict = {
    "nome_documento": "TERMO DE REFERÊNCIA – SERVIÇOS",
    "versao": "Jan/2026",
    "fonte": "Modelo Termo de Referência – Serviços – MPBA (Jan/2026)",
    "secoes": {
        "1_caracterizacao_objeto": {
            "1.1": {
                "titulo": "Objeto da Contratação",
                "obrigatorio": True,
                "nota": "Deve declarar que o objeto não é bem de luxo (Ato Normativo nº 004/2024)",
            },
            "1.2": {
                "titulo": "Código de Serviços / Ramo de Atividade (PDM)",
                "obrigatorio": True,
                "nota": (
                    "Informar o código PDM/Código de Serviços do Catálogo de Serviços. "
                    "Verificar no compras.gov.br se o código não está suspenso."
                ),
                "campo": "codigo_pdm_servicos",
            },
            "1.3": {
                "titulo": "Forma de Execução",
                "opcoes": {
                    "A": "Sob demanda (sem continuidade)",
                    "B": "Projeto específico (prazo determinado)",
                    "C": {
                        "descricao": "Serviços Continuados",
                        "sub_opcoes": {
                            "C1": "Mão de obra residente",
                            "C2": "Mão de obra não residente",
                            "C3": "Serviços de natureza continuada com dedicação exclusiva",
                            "C4": "Outros serviços continuados",
                        },
                        "exige_justificativa": True,
                    },
                },
            },
            "1.4": {
                "titulo": "Serviço de Engenharia",
                "nota": "Se serviço de engenharia: informar B.1 (descrição técnica) e B.2 (ART/RRT)",
                "campos_engenharia": ["B.1 – Descrição Técnica", "B.2 – ART/RRT"],
            },
        },
        "2_base_legal_habilitacao": {
            "2.1.1": {
                "titulo": "Base Legal",
                "lei": "Lei nº 14.133/2021",
                "artigo_servicos_comuns": "art. 75, inciso II",
                "artigo_engenharia": "art. 75, inciso I",
                "obrigatorio": True,
            },
            "2.1.2": {
                "titulo": "Divulgação no Portal MPBA",
                "opcao_a": "Não divulgar – exige justificativa",
                "opcao_b": {
                    "descricao": "Divulgar – informar e-mail, telefone e prazo em dias úteis",
                    "prazo_minimo_dias_uteis": 3,
                    "norma": "art. 75, §3º, Lei 14.133/2021",
                },
            },
            "2.2.1": "Habilitação Jurídica – Pessoa Jurídica ou Pessoa Física",
            "2.2.2": {
                "titulo": "Regularidade Fiscal, Social e Trabalhista",
                "certidoes_obrigatorias": [
                    "Certidão Conjunta Receita Federal + Dívida Ativa da União",
                    "Certidão de Regularidade com a Fazenda Estadual (SEFAZ sede)",
                    "Certidão de Regularidade com a Fazenda Municipal",
                    "CNDT – Certidão de Débitos Trabalhistas",
                    "CRF/FGTS – Certidão de Regularidade do FGTS",
                ],
            },
            "2.2.3": {
                "titulo": "Habilitação Técnica",
                "opcao_a": "Não exige comprovação de capacidade técnica",
                "opcao_b": "Exige – informar requisitos técnicos específicos",
            },
            "2.2.4": {
                "titulo": "Qualificação Econômico-Financeira",
                "opcoes": {
                    "A": "Não exige",
                    "B": "Certidão negativa de falência",
                    "C": "Balanço Patrimonial – exige justificativa",
                    "D": "Capital Social mínimo – máximo 10% do valor estimado; exige justificativa",
                    "E": "Outro – especificar",
                },
            },
        },
        "3_condicoes_execucao": {
            "3.1": "Regime de Execução (empreitada por preço global/unitário/tarefa)",
            "3.2": {
                "titulo": "Prazo para início após recebimento da Nota de Empenho",
                "prazo_minimo_dias_uteis": 10,
                "norma": "Ato Normativo MPBA nº 048/2024",
            },
            "3.3.1": {
                "titulo": "Local de Execução dos Serviços",
                "campos": ["Endereço completo", "CEP"],
                "obrigatorio": True,
            },
        },
        "apenso_i": {
            "titulo": "Apenso I – Planilha de Itens/Serviços",
            "obrigatorio": True,
            "nota": "Deve listar todos os itens com descrição, unidade, quantidade e valor estimado unitário e total.",
        },
    },
    "alertas_texto": {
        "texto_verde": "Texto exemplificativo em verde deve ser excluído do TR final",
        "texto_roxo": "Texto de orientação em roxo deve ser excluído do TR final",
    },
    "declaracao_nao_bem_luxo": {
        "norma": "Ato Normativo MPBA nº 004/2024",
        "obrigatorio": True,
        "texto_esperado": "o objeto desta contratação não se enquadra como bem de luxo",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TR AQUISIÇÕES – Termo de Referência – Aquisições (Jan/2026)
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_TR_AQUISICOES: dict = {
    "nome_documento": "TERMO DE REFERÊNCIA – AQUISIÇÕES",
    "versao": "Jan/2026",
    "fonte": "Modelo Termo de Referência – Aquisições – MPBA (Jan/2026)",
    "secoes": {
        "1_caracterizacao_objeto": {
            "1.1": {
                "titulo": "Objeto da Contratação",
                "obrigatorio": True,
                "nota": "Deve declarar que o objeto não é bem de luxo (Ato Normativo nº 004/2024)",
            },
            "1.2": {
                "titulo": "Código de Material (CATMAT) / Marca e Modelo",
                "obrigatorio": True,
                "catmat": {
                    "descricao": "Código CATMAT do objeto no Catálogo de Materiais (compras.gov.br)",
                    "campo": "codigo_catmat",
                },
                "marca_modelo": {
                    "opcao_a": "Não exige marca/modelo específico",
                    "opcao_b": {
                        "descricao": "Exige marca/modelo – justificativa obrigatória",
                        "norma": "art. 41, §1º, Lei 14.133/2021",
                    },
                    "opcao_c": {
                        "descricao": "Indica marca como referência de qualidade – justificativa obrigatória",
                    },
                },
            },
            "1.3": {
                "titulo": "Justificativa da Quantidade",
                "obrigatorio": True,
            },
            "1.4": {
                "titulo": "Forma de Fornecimento",
                "opcoes": {
                    "A": "Integral – entrega única",
                    "B": "Parcelado – conforme cronograma de entrega",
                    "C": "Consignação (mobiliário / almoxarifado)",
                    "D": "Outra – especificar",
                },
            },
        },
        "2_base_legal_habilitacao": {
            "2.1.1": {
                "titulo": "Base Legal",
                "lei": "Lei nº 14.133/2021",
                "artigo": "art. 75, inciso II",
                "obrigatorio": True,
            },
            "2.1.2": {
                "titulo": "Divulgação no Portal MPBA",
                "opcao_a": "Não divulgar – exige justificativa",
                "opcao_b": {
                    "descricao": "Divulgar – informar e-mail, telefone e prazo em dias úteis",
                    "prazo_minimo_dias_uteis": 3,
                    "norma": "art. 75, §3º, Lei 14.133/2021",
                },
            },
            "2.2.1": "Habilitação Jurídica",
            "2.2.2": {
                "titulo": "Regularidade Fiscal, Social e Trabalhista",
                "certidoes_obrigatorias": [
                    "Certidão Conjunta Receita Federal + Dívida Ativa da União",
                    "Certidão de Regularidade com a Fazenda Estadual",
                    "Certidão de Regularidade com a Fazenda Municipal",
                    "CNDT – Certidão de Débitos Trabalhistas",
                    "CRF/FGTS – Certidão de Regularidade do FGTS",
                ],
            },
            "2.2.3": "Habilitação Técnica (Opção A: não exige / Opção B: exige + requisitos)",
            "2.2.4": "Qualificação Econômico-Financeira (opções A a E)",
        },
        "3_condicoes_fornecimento": {
            "3.1": {
                "titulo": "Prazo para entrega após recebimento da Nota de Empenho",
                "prazo_minimo_dias_uteis": 10,
                "norma": "Ato Normativo MPBA nº 048/2024",
            },
            "3.2": {
                "titulo": "Local de Entrega dos Bens",
                "campos": ["Endereço completo", "CEP"],
                "obrigatorio": True,
            },
        },
        "apenso_i": {
            "titulo": "Apenso I – Planilha de Itens/Materiais",
            "obrigatorio": True,
            "nota": "Deve listar todos os itens com descrição, unidade, quantidade, valor unitário e total.",
        },
    },
    "alertas_texto": {
        "texto_verde": "Texto exemplificativo em verde deve ser excluído do TR final",
        "texto_roxo": "Texto de orientação em roxo deve ser excluído do TR final",
    },
    "declaracao_nao_bem_luxo": {
        "norma": "Ato Normativo MPBA nº 004/2024",
        "obrigatorio": True,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TABELA DE PREÇOS ORÇADOS
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_TABELA_PRECOS: dict = {
    "nome_documento": "TABELA DE PREÇOS ORÇADOS",
    "fonte": "Modelo Tabela de Preços Orçados – MPBA",
    "cabecalho_campos": [
        "Processo SEI nº",
        "Objeto",
        "Aviso prévio publicado no sítio eletrônico: SIM / NÃO",
        "Propostas recebidas: SIM / NÃO",
        "Data da publicação / Data das propostas",
    ],
    "colunas_itens": [
        "Item",
        "Descrição",
        "Unidade",
        "Quantidade",
        "Fornecedor A (CNPJ / Valor Unitário / Valor Total)",
        "Fornecedor B (CNPJ / Valor Unitário / Valor Total)",
        "Fornecedor C (CNPJ / Valor Unitário / Valor Total)",
        "Valor Unitário Médio ou Menor",
        "Valor Total",
    ],
    "rodape_campos": [
        "Metodologia: menor preço",
        "Motivação para a escolha dos fornecedores consultados",
        "Responsável pela pesquisa: Matrícula + Nome + Assinatura",
        "Valor Global da Contratação (R$)",
    ],
    "aviso_previo": {
        "campo": "aviso_previo_publicado",
        "valores": ["SIM", "NÃO"],
        "norma": "art. 75, §3º, Lei 14.133/2021",
        "prazo_minimo_dias_uteis": 3,
        "nota": "Quando aviso prévio = NÃO, verificar justificativa na Tabela ou no TR.",
    },
    "propostas_recebidas": {
        "campo": "propostas_recebidas",
        "valores": ["SIM", "NÃO"],
        "nota": "Quando propostas_recebidas = NÃO, documentar tentativa frustrada.",
    },
    "minimo_orcamentos": 3,
    "justificativa_abaixo_minimo": True,
}

# ─────────────────────────────────────────────────────────────────────────────
# MODELO DE PROPOSTA (Orçamento)
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_PROPOSTA: dict = {
    "nome_documento": "MODELO DE PROPOSTA",
    "fonte": "Modelos de Proposta – Aquisições e Serviços – MPBA",
    "campos_obrigatorios": [
        "Razão Social do fornecedor",
        "CNPJ ou CPF",
        "Endereço completo",
        "Telefone / E-mail",
        "Data da proposta",
        "Validade da proposta (prazo em dias corridos)",
        "Descrição dos itens (com quantidade e valor unitário)",
        "Valor total da proposta",
        "Banco / Agência / Conta Corrente (sem extrato ou saldo)",
        "Nome e assinatura do responsável (ou e-mail institucional de origem)",
    ],
    "validade_padrao_dias": 180,
    "dado_bancario_proibido": [
        "extrato bancário",
        "saldo disponível",
        "saldo anterior",
        "movimentação financeira",
    ],
    "forma_valida_sem_assinatura": "e-mail institucional de origem",
    "nota": (
        "Proposta recebida por e-mail institucional dispensa assinatura manuscrita, "
        "desde que o e-mail seja de domínio corporativo/oficial do fornecedor."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# DECLARAÇÃO DE NÃO EMPREGO DE MENOR
# Art. 7º, inciso XXXIII, CF/1988
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_DECLARACAO_MENOR: dict = {
    "nome_documento": "DECLARAÇÃO DE NÃO EMPREGO DE MENOR",
    "fonte": "Modelo Declaração Menor de Idade – MPBA",
    "base_legal": "Art. 7º, inciso XXXIII, da Constituição Federal de 1988",
    "termos_obrigatorios": [
        "não emprega menor de dezoito anos",
        "trabalho noturno",
        "trabalho perigoso",
        "trabalho insalubre",
        "não emprega menor de dezesseis anos",
        "salvo na condição de aprendiz",
    ],
    "campos_assinatura": [
        "Nome completo do declarante",
        "Cargo / Função",
        "Data",
        "Assinatura",
    ],
    "alertas": [
        "Verificar que a declaração menciona tanto o menor de 18 anos (noturno/perigoso/insalubre) "
        "quanto o menor de 16 anos (geral, salvo aprendiz)",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# DECLARAÇÃO RESOLUÇÃO CNMP Nº 37/2009
# ─────────────────────────────────────────────────────────────────────────────

ESTRUTURA_DECLARACAO_CNMP: dict = {
    "nome_documento": "DECLARAÇÃO – RESOLUÇÃO CNMP Nº 37/2009",
    "fonte": "Modelo Declaração CNMP 37/2009 – MPBA",
    "base_legal": "Resolução CNMP nº 37/2009",
    "termos_obrigatorios": [
        "Resolução nº 37",
        "CNMP",
        "2009",
        "não ocupa cargo",
        "não exerce função",
    ],
    "termo_proibido": {
        "texto": "CNJ nº 07/2005",
        "motivo": (
            "A Resolução CNJ nº 07/2005 foi declarada inconstitucional. "
            "Aceitar apenas a Resolução CNMP nº 37/2009."
        ),
    },
    "campos_assinatura": [
        "Nome completo do declarante",
        "Cargo / Função",
        "CNPJ / CPF",
        "Data",
        "Assinatura",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# CERTIDÕES OBRIGATÓRIAS
# ─────────────────────────────────────────────────────────────────────────────

CERTIDOES_OBRIGATORIAS: list[dict] = [
    {
        "id": "federal_divida_ativa",
        "nome": "Certidão Conjunta de Débitos Relativos a Tributos Federais e Dívida Ativa da União",
        "emissor": "Receita Federal do Brasil / PGFN",
        "site": "https://solucoes.receita.fazenda.gov.br",
        "validade_dias": 180,
        "pessoa": "PF e PJ",
    },
    {
        "id": "estadual",
        "nome": "Certidão de Regularidade Fiscal com a Fazenda Estadual",
        "emissor": "SEFAZ do Estado sede do fornecedor (SEFAZ-BA para fornecedores baianos)",
        "validade_dias": 180,
        "pessoa": "PF e PJ",
    },
    {
        "id": "municipal",
        "nome": "Certidão de Regularidade Fiscal com a Fazenda Municipal",
        "emissor": "Prefeitura do município sede do fornecedor",
        "validade_dias": 180,
        "pessoa": "PF e PJ",
    },
    {
        "id": "cndt",
        "nome": "Certidão Negativa de Débitos Trabalhistas (CNDT)",
        "emissor": "Tribunal Superior do Trabalho (TST)",
        "site": "https://cndt.tst.jus.br",
        "validade_dias": 180,
        "pessoa": "PJ",
    },
    {
        "id": "fgts_crf",
        "nome": "Certificado de Regularidade do FGTS (CRF)",
        "emissor": "Caixa Econômica Federal",
        "validade_dias": 30,
        "pessoa": "PJ",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# REGRAS – ORÇAMENTOS / PROPOSTAS
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_ORCAMENTOS: dict = {
    "minimo_orcamentos": 3,
    "justificativa_abaixo_minimo": True,
    "norma": "art. 75, §3º, Lei 14.133/2021 + Instrução Normativa SEGES/ME",
    "descricao": (
        "Devem ser obtidos, no mínimo, 3 (três) orçamentos/propostas de fornecedores distintos. "
        "Caso não seja possível obter o mínimo, justificar e documentar as tentativas frustradas."
    ),
    "validade_padrao_dias": 180,
    "campos_minimos_proposta": [
        "razao_social",
        "cnpj_cpf",
        "endereco",
        "data_proposta",
        "valor_total",
        "assinatura_ou_email",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# REGRAS – AVISO PRÉVIO
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_AVISO_PREVIO: dict = {
    "prazo_minimo_dias_uteis": 3,
    "norma": "art. 75, §3º, Lei 14.133/2021",
    "veiculo": "Sítio eletrônico oficial do MPBA (Portal de Contratações)",
    "campo_tabela": "aviso_previo_publicado",
    "descricao": (
        "O aviso de contratação direta deve ser divulgado no Portal de Contratações do MPBA "
        "com antecedência mínima de 3 (três) dias úteis, contados da data pretendida "
        "para a contratação, exceto nos casos de comprovada urgência."
    ),
    "excecao": "Comprovada urgência – documentar justificativa no processo",
}

# ─────────────────────────────────────────────────────────────────────────────
# REGRAS – DOCUMENTO BANCÁRIO
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_DOCUMENTO_BANCARIO: dict = {
    "norma": "Ato Normativo MPBA nº 048/2024",
    "campos_permitidos": [
        "Banco",
        "Agência",
        "Número da conta corrente",
        "Tipo de conta",
        "Nome/Razão Social do titular",
        "CNPJ/CPF do titular",
    ],
    "campos_proibidos": [
        "Extrato bancário",
        "Saldo disponível",
        "Saldo anterior",
        "Movimentação financeira",
        "Histórico de transações",
        "Limite de crédito",
    ],
    "descricao": (
        "O comprovante de dados bancários deve conter apenas os dados de identificação "
        "da conta (banco, agência, número, titular). Não é permitida a inclusão de "
        "extratos ou saldos – o fornecedor deve ocultar ou entregar documento que "
        "contenha apenas os dados bancários."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# REGRAS – PDM / CÓDIGO DE SERVIÇOS / CATMAT
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_PDM_CATMAT: dict = {
    "norma": "Instrução Normativa SEGES/ME + Ato Normativo MPBA nº 048/2024",
    "pdm": {
        "descricao": "Padrão Descritivo de Material – código numérico do item no CATMAT",
        "site_consulta": "https://www.compras.gov.br/catmat",
        "status_invalidos": ["suspenso", "inativo", "cancelado"],
        "campo_tr": "codigo_pdm_material",
    },
    "codigo_servicos": {
        "descricao": "Código de Serviços no Catálogo de Serviços (compras.gov.br)",
        "site_consulta": "https://www.compras.gov.br/catalogo-servicos",
        "status_invalidos": ["suspenso", "inativo", "cancelado"],
        "campo_tr": "codigo_pdm_servicos",
    },
    "catmat": {
        "descricao": "Código do material no Catálogo de Materiais – CATMAT",
        "site_consulta": "https://www.compras.gov.br/catmat",
        "campo_tr": "codigo_catmat",
    },
    "alerta": (
        "Códigos PDM/CATMAT suspensos não podem ser utilizados em novos processos de contratação. "
        "Verificar a situação do código no compras.gov.br antes de prosseguir."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# REGRAS – GESTOR / FISCAL – SEGREGAÇÃO DE FUNÇÕES
# ─────────────────────────────────────────────────────────────────────────────

REGRAS_GESTOR_FISCAL: dict = {
    "norma": "Art. 117 da Lei nº 14.133/2021 + Ato Normativo MPBA nº 048/2024",
    "descricao": (
        "O Gestor do Contrato não pode ser simultaneamente Fiscal Administrativo ou Técnico. "
        "O Executor Orçamentário não pode ser o mesmo servidor designado como Fiscal. "
        "Obrigatória a segregação de funções entre gestor, fiscal e executor orçamentário."
    ),
    "regras": [
        "Gestor ≠ Fiscal Administrativo",
        "Gestor ≠ Fiscal Técnico",
        "Executor Orçamentário ≠ Fiscal (qualquer)",
    ],
    "campos_manifestacao_gestor": [
        "Código PDM/Código de Serviços (compras.gov.br)",
        "Nome do Gestor Orçamentário responsável",
        "Nome do Executor Orçamentário",
        "Nome do Fiscal Administrativo",
        "Nome do Fiscal Técnico (se aplicável)",
        "Valor global da contratação (R$)",
        "Assinatura do Gestor",
    ],
    "sicaf": {
        "obrigatorio": True,
        "descricao": (
            "O fornecedor deve estar regularmente inscrito no SICAF "
            "(Sistema de Cadastramento Unificado de Fornecedores). "
            "Caso não esteja, documentar excepcionalidade e obter os documentos equivalentes."
        ),
        "norma": "art. 87, Lei 14.133/2021",
        "excecao": (
            "Quando o fornecedor não estiver inscrito no SICAF, exigir todos os documentos "
            "de habilitação individualmente, conforme o TR."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# NORMAS – DISPENSA DE LICITAÇÃO COM CONTRATO PADRÃO (DL COM CONTRATO)
# Fonte: Base de Conhecimento MPBA – Contratos Padronizados
# ─────────────────────────────────────────────────────────────────────────────

NORMAS_CONTRATO_PADRAO: dict = {
    "modalidade": "Dispensa de Licitação Não Eletrônica – Com Contrato Padrão",
    "descricao": (
        "Variant de DL que utiliza minutas de contrato pré-aprovadas pela ATJ e pela SGA. "
        "Permite agilidade na contratação pois dispensa análise jurídica ad hoc, "
        "desde que respeitado o Procedimento – Contrato Padrão vigente."
    ),
    "lei_federal": "Lei nº 14.133/2021",
    "ato_normativo_mpba": "Ato Normativo MPBA nº 048/2024",
    "ato_normativo_pagamento": "Ato Normativo MPBA nº 036/2024, art. 18, §1º",
    "documentos_obrigatorios": [
        "DFD – Documento de Formalização da Demanda",
        "Termo de Referência (Serviços ou Aquisições)",
        "Tabela de Preços Orçados",
        "Orçamentos (mínimo 3)",
        "Certidão de Idoneidade (TCU, CNJ, CEIS, ComprasNet-BA, Portal MPBA)",
        "Documentos da empresa (Cartão CNPJ, SICAF, certidões fiscais)",
        "Declaração de Não Emprego de Menor (art. 7º, XXXIII, CF/1988)",
        "Declaração – Resolução CNMP nº 37/2009",
        "Procedimento – Contrato Padrão (aprovado ATJ + SGA)",
        "Minuta do Contrato (campos em vermelho preenchidos, formato DOCX)",
        "Portaria de designação de Gestor, Fiscal Administrativo e Fiscal Técnico",
        "Executor Orçamentário / Informações Orçamentárias",
        "Memória de Cálculo (Limite art. 75 §1º)",
        "Demonstrativo FIPLAN",
        "Manifestação do Gestor Orçamentário",
        "Manifestações de Ciência (Gestor e Fiscais)",
    ],
    "documentos_especificos_por_objeto": {
        "agua_mineral": ["Alvará de Vigilância Sanitária do fornecedor"],
        "mensageiro_motoboy": [
            "CNH (Carteira Nacional de Habilitação) do condutor",
            "Documento do veículo utilizado",
        ],
        "servicos_monitoramento": {
            "restricao_mei": True,
            "motivo": (
                "Serviços de monitoramento eletrônico exigem estrutura operacional mínima "
                "incompatível com a natureza jurídica de MEI (Microempreendedor Individual)."
            ),
        },
    },
    "fluxo_15_etapas": [
        "1. Recebimento do processo pela DCCL",
        "2. Verificação de documentação – saneamento",
        "3. Autorização de publicação do aviso (SICAF obrigatório)",
        "4. Publicação do aviso no Portal MPBA (mínimo 3 du)",
        "5. Coleta de propostas / orçamentos",
        "6. Seleção do fornecedor (menor preço)",
        "7. Verificação de idoneidade (TCU, CNJ, CEIS, ComprasNet-BA, Portal MPBA)",
        "8. Cadastro do usuário externo (fornecedor) no SEI",
        "9. Envio da Minuta do Contrato ao fornecedor pelo SEI",
        "10. Assinatura do contrato pelas partes",
        "11. Publicação da contratação no Portal MPBA",
        "12. Emissão da Nota de Empenho pelo FIPLAN",
        "13. Início da execução contratual",
        "14. Processo de pagamento (Ato Normativo 036/2024 art. 18 §1º)",
        "15. Publicação no PNCP e finalização no FIPLAN",
    ],
}

REGRAS_CERTIDAO_IDONEIDADE: dict = {
    "nome_documento": "Certidão de Idoneidade",
    "descricao": (
        "Consulta obrigatória a todos os cadastros de fornecedores impedidos/suspensos "
        "antes de autorizar a contratação."
    ),
    "cadastros_obrigatorios": [
        {
            "id": "tcu",
            "nome": "TCU – Cadastro de Empresas Inidôneas e Suspensas (CEIS/CNEP)",
            "site": "https://certidoes-apf.apps.tcu.gov.br",
            "campo": "tcu_inidoneidade",
        },
        {
            "id": "cnj",
            "nome": "CNJ – Cadastro Nacional de Condenações Cíveis por Improbidade",
            "site": "https://www.cnj.jus.br/improbidade_adm/consultar_requerido.php",
            "campo": "cnj_improbidade",
        },
        {
            "id": "ceis",
            "nome": "CEIS – Cadastro de Empresas Inidôneas e Suspensas (CGU)",
            "site": "https://www.portaltransparencia.gov.br/sancoes/ceis",
            "campo": "ceis_cgu",
        },
        {
            "id": "comprasnet_ba",
            "nome": "ComprasNet-BA – Fornecedores suspensos no Estado da Bahia",
            "site": "https://www.compras.ba.gov.br",
            "campo": "comprasnet_ba",
        },
        {
            "id": "portal_mpba",
            "nome": "Portal MPBA – Fornecedores com contratos rescindidos ou suspensos",
            "campo": "portal_mpba",
        },
    ],
    "resultado_esperado": "Sem restrições em todos os cadastros",
    "acao_se_impedido": (
        "Fornecedor impedido ou suspenso em qualquer cadastro NÃO pode ser contratado. "
        "Selecionar o próximo colocado ou reiniciar o processo de cotação."
    ),
}

REGRAS_MINUTA_CONTRATO: dict = {
    "nome_documento": "Minuta do Contrato",
    "formato_obrigatorio": "DOCX (arquivo editável – Microsoft Word)",
    "descricao": (
        "Minuta pré-aprovada pela ATJ e SGA. Apenas os campos marcados em vermelho "
        "devem ser preenchidos pela unidade. Nenhuma cláusula pode ser alterada."
    ),
    "campos_em_vermelho": [
        "Número do processo SEI",
        "Data de assinatura do contrato",
        "Identificação completa do contratado (Razão Social, CNPJ, endereço)",
        "Nome e qualificação do representante legal do contratado",
        "Objeto específico (descrição do item/serviço conforme TR)",
        "Valor global do contrato (R$)",
        "Prazo de vigência (data de início e término)",
        "Dotação orçamentária (unidade, natureza de despesa, fonte)",
        "Nome e matrícula do Gestor do Contrato",
        "Nome e matrícula do Fiscal Administrativo",
        "Nome e matrícula do Fiscal Técnico (se aplicável)",
    ],
    "restricoes": [
        "Nenhuma cláusula originalmente pré-aprovada pode ser suprimida ou alterada",
        "Apenas os campos em vermelho devem ser editados",
        "Após preenchimento, converter para PDF para assinatura no SEI",
    ],
    "procedimento_aprovacao": "Aprovado pela Assessoria Técnico-Jurídica (ATJ) + SGA (MPBA)",
    "norma": "Ato Normativo MPBA nº 048/2024",
}

REGRAS_PORTARIA_DESIGNACAO: dict = {
    "nome_documento": "Portaria de Designação",
    "descricao": (
        "Portaria do Procurador-Geral de Justiça ou do Secretário-Geral designando "
        "formalmente o Gestor do Contrato e o(s) Fiscal(is)."
    ),
    "campos_obrigatorios": [
        "Número e data da Portaria",
        "Nome completo e matrícula do Gestor do Contrato",
        "Nome completo e matrícula do Fiscal Administrativo",
        "Nome completo e matrícula do Fiscal Técnico (se houver)",
        "Referência ao processo SEI e ao contrato",
        "Assinatura da autoridade competente",
    ],
    "segregacao_obrigatoria": [
        "Gestor ≠ Fiscal Administrativo",
        "Gestor ≠ Fiscal Técnico",
        "Os servidores designados devem ter Manifestação de Ciência no processo",
    ],
    "norma": "Art. 117, Lei 14.133/2021 + Ato Normativo MPBA nº 048/2024",
}

REGRAS_USUARIO_EXTERNO_SEI: dict = {
    "descricao": (
        "O representante legal do fornecedor (contratado) deve ser cadastrado como "
        "usuário externo no SEI-MPBA para receber e assinar a Minuta do Contrato "
        "eletronicamente, antes da formalização da contratação."
    ),
    "etapas": [
        "Solicitar ao fornecedor: e-mail, CPF do representante legal, telefone",
        "Cadastrar no SEI como usuário externo (módulo Usuários Externos)",
        "Enviar Minuta do Contrato ao fornecedor pelo SEI para assinatura",
        "Aguardar assinatura eletrônica do fornecedor no SEI",
    ],
    "campo_verificacao": "usuario_externo_sei_cadastrado",
    "norma": "Instrução de Trabalho MPBA – SEI Usuários Externos",
}

REGRAS_PAGAMENTO_CONTRATO: dict = {
    "norma": "Ato Normativo MPBA nº 036/2024, art. 18, §1º",
    "descricao": (
        "O processo de pagamento deve ser iniciado dentro do prazo estabelecido "
        "no Ato Normativo nº 036/2024, art. 18, §1º. "
        "O gestor do contrato é responsável por instruir o processo de pagamento."
    ),
    "responsavel": "Gestor do Contrato",
    "documentos_pagamento": [
        "Nota Fiscal / Fatura do fornecedor",
        "Atestado de execução/recebimento pelo Fiscal Técnico",
        "Atestado de conformidade administrativa pelo Fiscal Administrativo",
        "Emissão de Nota de Empenho no FIPLAN",
    ],
}
