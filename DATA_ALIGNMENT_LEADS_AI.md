# Alinhamento de dados com Leads AI (somente referência)

Este produto é **independente**. A ideia é **reutilizar o mesmo “formato mental” de dados** que o Leads AI já usa, para:

- importar um JSON exportado no futuro (se você quiser), ou  
- manter times/Dhawk falando a mesma língua entre produtos.

Nada aqui importa código ou banco do repositório `LEADS_AI`.

---

## 1. Onboarding / briefing (frontend state → seu `briefing` table)

Campos equivalentes ao `onboardingStore` do Leads AI (`web_v2/src/data/onboardingStore.ts`):

| Campo conceitual | Uso no Pilotgram |
|------------------|------------------|
| `plan` | Plano de assinatura do **novo** SaaS |
| `email`, `instagram`, `whatsapp` | Contato + handle alvo |
| `mission`, `enemy`, `pain`, `dream`, `dreamClient`, `method` | Contexto para LLM |
| `toneVoice`, `brandValues`, `offerDetails`, `differentiation` | Tom e posicionamento |
| `posts[]` com `link`, `views`, `likes`, `comments`, `shares`, `saves`, `conversions`, `creativeTheme?` | Histórico manual ou enriquecido pela API |
| `accessToken`, `accountId` (Meta) | **Tokens do Pilotgram** — armazenar no backend com criptografia, não só localStorage |

---

## 2. Relatório / estratégia com `roteiros`

No backend do Leads AI, o pipeline trabalha com JSON de estratégia que inclui chave **`roteiros`** (lista de posts/roteiros; imagens opcionais em `image_url` após o Artisan).

Para o Pilotgram, você pode definir um tipo **compatível** no seu código, por exemplo:

```json
{
  "roteiros": [
    {
      "titulo": "string",
      "legenda": "string",
      "direcao_visual": "string",
      "image_url": "string | null",
      "creativeTheme": "string | null"
    }
  ]
}
```

Os nomes exatos podem divergir se você versionar (`schema_version: 1`), mas manter **`roteiros` como array** facilita qualquer export/import futuro.

---

## 3. O que não prometer com base só na API

- **Lista completa de “quem curtiu”** post a post: frequentemente **indisponível** ou restrita; use métricas agregadas.  
- **DM / automação fora das APIs oficiais**: fora de escopo deste brief ou sujeito a produtos separados (ex.: Rob Chat) e políticas distintas.

---

## 4. Prefixo de tabelas (se compartilhar Supabase)

Se no futuro o banco for o mesmo projeto Supabase de outros SaaS, use prefixo dedicado, por exemplo:

`igca_users`, `igca_ig_accounts`, `igca_scheduled_posts`, …

Evita colisão com `la_*` do Leads AI.
