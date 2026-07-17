# Spec — Fase 2: Setor de Manutenção

> Decisões de produto (17/07/2026): obra entregue é entidade própria (não
> mistura com as obras em execução); o setor agenda e o encarregado executa;
> registro de manutenção tem fotos.

## Objetivo

O setor de manutenção guarda as obras já entregues (clientes antigos) e o
histórico de manutenções feitas em cada uma. O setor agenda as manutenções
com data e responsável; o encarregado de manutenção loga e vê **a semana
dele**, e ao concluir registra o que foi feito, com fotos.

## Papéis e acesso

- Novo papel `manutencao` ("Setor de Manutenção") em `PAPEIS`.
- Nova ferramenta `manutencao` ("Manutenções") em `FERRAMENTAS`.
- **Gestor** (papel `manutencao` ou admin, com a ferramenta liberada):
  cadastra/edita obras entregues, agenda/edita/exclui manutenções, vê tudo.
- **Executor** (demais usuários com a ferramenta liberada, ex.: papel
  `encarregado`): vê apenas as manutenções atribuídas a ele ("minha semana"),
  conclui com descrição do serviço e envia fotos.
- Quem não tem a ferramenta: 403. Executor tentando agir como gestor: 403.
  Recurso de outro executor: 404 (não vaza).

## Modelo de dados (tabelas novas — só `create_all`, sem ALTER)

- `ObraEntregue`: `id, cliente, endereco, data_entrega (date), fim_garantia
  (date), observacoes, criado_em`.
- `Manutencao`: `id, obra_entregue_id, titulo, detalhes, responsavel_id,
  criador_id, data_agendada (date), status (agendada | concluida),
  descricao_realizada, concluida_em, criado_em`.
- `FotoManutencao`: `id, manutencao_id, arquivo, ordem, criado_em` —
  arquivos em `uploads/manutencao/<manutencao_id>/`, processados pelo
  `processar_imagem` existente.

## Rotas

- `GET /manutencao` — gestor: obras entregues + próximas manutenções;
  executor: "minha semana" (atrasadas / semana / próximas, como nas tarefas).
- `POST /manutencao/obras/criar` · `POST /manutencao/obra/<id>/editar` — gestor.
- `GET /manutencao/obra/<id>` — gestor: dados do cliente + histórico completo.
- `POST /manutencao/obra/<id>/agendar` — gestor; responsável precisa ter a
  ferramenta `manutencao` liberada (400 caso contrário).
- `POST /manutencao/<id>/concluir` — responsável ou gestor; grava
  `descricao_realizada` (obrigatória) e `concluida_em`.
- `POST /manutencao/<id>/fotos` — responsável ou gestor; upload processado.
- `GET /manutencao/foto/<id>` — serve a foto só para gestor ou responsável.
- `POST /manutencao/<id>/excluir` — gestor.

## Critérios de aceite (viram testes)

1. Gestor cria obra entregue; executor recebe 403 e nada muda; sem a
   ferramenta, 403.
2. Gestor agenda manutenção para um executor; responsável sem a ferramenta
   `manutencao` → 400.
3. Executor vê na "minha semana" apenas as manutenções dele; a página de
   obra entregue responde 404 para executor.
4. Executor conclui a própria manutenção (descrição obrigatória → 400 sem
   ela); manutenção de outro executor → 404; gestor conclui qualquer uma.
5. Foto enviada pelo responsável é processada (JPEG ≤ 2000px) e servida só
   para gestor/responsável; outro usuário → 404.
6. Obra entregue mostra o histórico (concluídas com descrição e data).
7. Suíte inteira verde; tabelas novas criadas por `create_all` (verificar
   `init_db` no banco local).

## Casos de erro

Cliente vazio → 400 · título vazio → 400 · data inválida → 400 ·
responsável inválido/sem ferramenta → 400 · concluir sem descrição → 400.

## Fora de escopo (v1)

Solicitações vindas do cliente final; garantia com alertas automáticos;
relatório PDF/PPTX da manutenção; notificações externas.
