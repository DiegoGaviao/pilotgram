# Pré-requisitos (viabilidade real)

Já existem produtos que **agendam** e **sugerem** conteúdo (Buffer, Later, Hootsuite, Metricool, Meta Business Suite, etc.). O que você está desenhando junta **autoridade da API Meta**, **análise do que funcionou no seu histórico** e **LLM no formato Leads AI** com **aprovação humana** — combinação própria, ainda que partes isoladas existam no mercado.

## Sim, é factível — com estes requisitos

### 0. “Quase ninguém é Business/Creator” — o que isso muda na prática

Muita gente **percebe** o perfil como “pessoal”, mas na Meta a distinção importante para **API** é outra:

- **Conta pessoal (só consumo / sem modo profissional)** — a **Instagram Graph API** que usamos para **publicar na hora certa** e **insights estáveis** **não** cobre esse modo. Não é uma escolha do nosso SaaS; é **limite da plataforma**.
- **Conta profissional** — no app Instagram: *Configurações → Tipo de conta → Mudar para conta profissional*. Você escolhe **Criador** ou **Empresa**.  
  - É **gratuito**.  
  - **Não** exige CNPJ (quem é pessoa física costuma usar **Criador**).  
  - Continua sendo “seu” perfil; muda o que a Meta expõe para ferramentas conectadas.

**Para o seu produto:** o onboarding pode ser explícito em uma frase: *“Para agendar e publicar pela API, o Instagram precisa estar em modo Criador ou Empresa e ligado a uma Página do Facebook — leva cerca de dois minutos.”* Quem **recusar** deixar de ser conta puramente pessoal no sentido da API fica com alternativas **fora** do caminho oficial: **pacote para postar manual** (legenda + mídia + lembrete) ou automação de browser (**arriscado**, possível violação de termos). O posicionamento do Pilotgram como **ferramenta séria** combina com **Creator/Empresa + API**.

### 1. Tipo de conta Instagram (requisito técnico)

- Precisa ser **Instagram Business** ou **Instagram Creator** (ambos são contas **profissionais** no app).
- Essa conta deve estar **vinculada a uma Página do Facebook** que você administra.

**Conta pessoal** no sentido da Meta (sem modo profissional / sem vínculo com Página), **não** entra no fluxo oficial de publicação e insights que este produto usa.

### 2. Login: não é “senha do Instagram no seu site”

O caminho **oficial** é **Facebook Login (Meta)** com escopos corretos: o usuário entra com a **conta Facebook** que administra a Página/Instagram, **autoriza o app**, e você recebe **tokens** para a Graph API.

Na interface pode parecer “escolher qual Instagram usar”, mas tecnicamente a autorização vem da **Meta OAuth**, não de um formulário de login Instagram no seu SaaS.

### 2.1 E se eu oferecer o serviço pelo **meu** Business Manager, “entrando” o cliente lá?

**Dá**, e é um modelo **muito usado por agências e SaaS B2B**: **um app Meta só seu** (criado na sua conta / vinculado ao seu portfólio de negócios), e cada **cliente autoriza** o uso dos **ativos dele** (Página do Facebook + Instagram profissional ligado a essa Página).

O que isso **melhora** para você:

- O cliente **não** precisa criar app em developers.facebook.com nem entender Meta for Developers.
- Você centraliza **App Review**, configuração de produtos (Facebook Login, Instagram API) e políticas de privacidade **uma vez**.
- O fluxo típico continua sendo: alguém com **permissão na Página** do cliente faz **login e aceita os escopos** do **seu** app (OAuth) — ou você usa fluxos de **parceiro / compartilhamento de ativos** no Business Manager, conforme a Meta documenta na época (nomes de tela mudam; a ideia é **delegação de acesso**, não “sumir com a conta do cliente”).

O que isso **não** resolve:

- **Não** elimina a necessidade de o Instagram do cliente ser **Criador/Empresa** e estar **ligado a uma Página**. Colocar o cliente no seu BM **não converte** perfil “pessoal” no sentido da API em perfil publicável pela Graph API.
- Você continua precisando de **tokens válidos** (por cliente / por conjunto de ativos) e de **isolamento** no seu backend (multi-tenant), além de **contrato** claro (você publicando em nome deles, retenção de dados, LGPD).

**Resumo:** sim, pode ser **seu** Business Manager + **seu** app + cliente com **acesso delegado** aos ativos dele; isso é **compatível** com o Pilotgram. Só não confunda com “o cliente não precisa mais de Instagram profissional” — **precisa**, a menos que você ofereça outro modo de entrega (ex.: só rascunho + post manual).

### 3. App na Meta

- App criado em [developers.facebook.com](https://developers.facebook.com/).
- **Instagram Graph API** + **Facebook Login** configurados.
- **Modo desenvolvimento** até passar pelo que a Meta exige para produção (**App Review** para escopos sensíveis como publicação e insights).
- URLs de **OAuth redirect** cadastradas em produção: `https://www.dhawk.com.br/projetos/Pilotgram/oauth/callback` (alinhado a `META_OAUTH_REDIRECT_URI` no backend).

### 4. O que dá para coletar (expectativa honesta)

| Dá para ter (via API) | Nem sempre / depende de permissão |
|------------------------|-----------------------------------|
| Lista de mídias recentes, legenda, tipo, link, timestamp | “Quem curtiu” em lista detalhada |
| Contagens como likes/comentários quando expostas no objeto | Algumas métricas só com `instagram_manage_insights` + revisão |
| Insights por mídia (alcance, impressões, engajamento) onde a API permitir | Dados de concorrentes ou perfis não conectados |

O padrão “tipo de post + tom da legenda + métricas → LLM aprende padrão” **funciona** com o que a API devolve; não prometa CRM de likers.

### 5. Agendamento

A Meta **não é obrigada** a ter um “agendador interno” único para tudo que você quer. O padrão de produtos SaaS é: **seu banco** guarda `publish_at` e um **worker** chama a **Content Publishing API** na hora — equivalente funcional ao que você descreveu.

### 6. LLM + questionário estilo Leads AI

Factível: mesmo briefing + pipeline de geração de `roteiros`, com sua própria chave OpenAI/DeepSeek no backend do Pilotgram (código **inspirado**, não importando o repo Leads AI).

---

## Resumo em uma frase

**Sim:** conectar via Meta, escolher IG Business/Creator, puxar o que a API permite, mandar para LLM, gerar posts no formato Leads-like, aprovar e **publicar/agendar pela API** — desde que conta e app estejam nos trilhos acima.
