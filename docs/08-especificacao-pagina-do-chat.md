# Especificação: melhorias na página do chat

Este documento descreve o que precisa mudar na página do chat. A primeira parte trata dos filtros da busca e da tela inicial, e a segunda, no fim, reúne o que encontrei ao revisar a página como um todo, com a ordem em que pretendo fazer cada coisa. O filtro já funciona de ponta a ponta, com nota, categoria e entrega, mas quem abre a página não percebe que ele existe e, quem percebe, não entende o que cada opção faz. Os problemas são de apresentação, e por isso as mudanças ficam todas em `frontend/`, sem alterar a API nem a busca.

## O que está errado hoje

O filtro aparece como uma linha cinza no rodapé, colada ao campo da pergunta, com o texto "Filtros da busca" e a palavra "nenhum". Ela tem o mesmo peso visual de uma nota de rodapé e nada indica que é clicável. A palavra "nenhum" descreve o estado do sistema e não o que importa para o gestor, que é saber onde a busca está olhando.

Quando o painel abre, ele mostra um formulário: cinco caixas de seleção numeradas de 1 a 5, sem dizer que são notas, dois menus suspensos e um parágrafo de quatro linhas com regras técnicas, como a de que pedidos com produtos de várias categorias ficam de fora. O painel abre dentro do campo fixo do rodapé e empurra a pergunta para cima. No celular, aberto, ele ocupa mais da metade da tela e cobre a conversa.

As caixas de seleção têm cerca de 16 pixels de lado, abaixo dos 44 pixels que as orientações de acessibilidade recomendam para toque. A lista de categorias é um menu suspenso nativo com mais de setenta nomes, difícil de percorrer. Depois de enviar uma pergunta, o filtro continua ligado sem nenhum aviso, e quem filtrou as notas baixas para uma pergunta pode esquecer disso na seguinte.

A tela inicial também não indica por onde começar. Ela reúne título, parágrafo, quatro cartões de exemplo, uma nota explicativa, o filtro e o campo de pergunta, e nada diz que o campo é o ponto de partida.

## Princípios que orientam a mudança

Uma função importante precisa parecer clicável, e o seu estado precisa ser visível sem abrir nada. O rótulo deve dizer o que acontece para a pessoa, e não o que o sistema guarda. Explicações longas ficam fora do caminho e aparecem só quando fazem diferença. Toda escolha deve ser reversível num clique, no lugar onde foi feita. Os alvos de toque têm pelo menos 44 pixels. O teclado e o leitor de tela precisam chegar a todas as opções.

## Faixa de filtros acima do campo de pergunta

Acima do campo de pergunta fica uma faixa com o rótulo "Filtrar a busca" e três botões em forma de pílula: Nota, Categoria e Entrega. Cada botão mostra o seu estado sem abrir nada. Sem filtro, o botão traz só o nome. Com filtro, ele muda de cor e passa a mostrar o valor, como "Nota: 1 e 2" ou "Entrega: com problema", e ganha um pequeno x que remove só aquele filtro. Quando há pelo menos um filtro ativo, aparece ao lado o botão "Limpar tudo".

Perto da faixa, uma linha de apoio diz onde a busca está olhando. Sem filtros, o texto é "Buscando em todas as avaliações". Com filtros, o texto é "Buscando só em avaliações com nota 1 e 2 e entregas com problema". Essa linha substitui a palavra "nenhum" e é a única explicação que fica sempre à vista.

## O que cada botão abre

O botão de nota abre um pequeno menu com cinco botões grandes, de "1 estrela" a "5 estrelas", que podem ser marcados juntos. Marcar nenhum equivale a todas as notas. O menu mostra também dois atalhos, "Notas baixas" (1 e 2) e "Notas altas" (4 e 5), porque são as perguntas mais comuns de um gestor, como "o que reclamam nas notas baixas".

O botão de entrega abre uma lista de quatro opções com nomes completos: "Entregue no prazo", "Entregue com atraso", "Não entregue" e "Com problema (atraso ou não entregue)". Só uma opção vale por vez, e escolher a mesma de novo a desmarca.

O botão de categoria abre uma lista com campo de busca, porque são mais de setenta categorias. Digitar "cama" já deixa só "Cama mesa banho". Os nomes aparecem como hoje, com a inicial maiúscula e sem sublinhados. A única exceção de regra que o gestor precisa saber, a de que pedidos com produtos de várias categorias ficam de fora, aparece como uma linha de apoio no rodapé desse menu e em nenhum outro lugar. O mesmo vale para a dica de que o filtro de entrega deixa de fora os pedidos sem essa informação, que aparece só dentro do menu de entrega.

A lista de categorias vem da API, que só responde com a chave de acesso. Por isso o menu de categoria tem quatro estados. Sem a chave, ele mostra "Digite a chave de acesso para ver as categorias", e o foco vai para o campo da chave. Durante a carga, mostra "Carregando as categorias". Se a carga falhar, mostra a mensagem do erro e um botão "Tentar de novo". Quando a busca por nome não encontra nada, mostra "Nenhuma categoria com esse nome". Hoje a falha é silenciosa e o menu fica só com "Todas", sem explicação.

Cada menu fecha ao clicar fora, ao apertar Esc e ao escolher uma opção que só admite uma escolha. O foco volta para o botão que o abriu.

## O filtro como parte da conversa

O filtro usado numa pergunta continua aparecendo no balão da pergunta, como "Filtros: nota 1 · com problema", para que o histórico mostre com que critério cada resposta foi dada. A próxima pergunta mantém os filtros ativos, e a faixa mostra isso de forma explícita com a linha de apoio. Quem quiser perguntar sem filtro remove os botões ou usa "Limpar tudo". Quando a resposta vem com notas deduzidas da própria pergunta, como em "E nas notas altas?", a página continua mostrando o aviso que já existe, e a faixa não muda, porque essa dedução vale só para aquela resposta.

Todas as perguntas usam os filtros ativos, inclusive as dos cartões de exemplo e as sugeridas depois de cada resposta. A regra é uma só, e a linha de apoio está sempre à vista para lembrar o critério. O botão "Tentar de novo" de um erro repete a pergunta com os filtros que ela tinha quando foi feita, mesmo que a faixa tenha mudado depois. "Nova conversa" limpa os filtros junto com a conversa. Os filtros não ficam guardados no navegador: recarregar a página volta a buscar em todas as avaliações. Enquanto uma pergunta está em andamento, a faixa continua utilizável, e a mudança vale só para a pergunta seguinte.

Quando o gestor marca notas na faixa e também cita notas na pergunta, a API usa as da faixa. Nesse caso a página não mostra o aviso de notas deduzidas, e o balão da pergunta mostra as notas da faixa, que foram as usadas.

## Quando o filtro deixa a busca sem resultado

Um filtro apertado, como uma categoria pequena com nota 1, pode deixar a busca com poucos comentários ou com nenhum. Hoje a resposta sai como "Sem evidência" ou "Evidência fraca", sem dizer que o motivo pode ser o filtro. Quando a resposta vem com um desses dois avisos e a pergunta foi feita com filtros, o aviso ganha uma frase a mais, "A busca estava restrita a nota 1 e Cama mesa banho", e um botão "Perguntar sem filtros", que repete a mesma pergunta em todas as avaliações, sem mexer na faixa.

## No celular

Em telas de até 640 pixels, cada menu abre como uma folha que sobe da parte de baixo da tela, por cima da conversa, com cantos arredondados, título e um botão "Fechar". A escolha vale assim que é feita, como no computador, e a folha de entrega e a de categoria fecham sozinhas depois da escolha; a de nota fica aberta, porque aceita mais de uma. Tocar fora da folha também a fecha. Os botões das opções têm 48 pixels de altura. A faixa de filtros rola na horizontal, numa linha só, para não ocupar duas linhas do rodapé. O campo de pergunta e o botão "Perguntar" nunca saem da tela.

Entre 641 e 900 pixels, como num tablet ou numa janela estreita, vale o comportamento do computador, com os menus abrindo para cima, e a faixa quebra em duas linhas se os três botões com valor não couberem.

## Tela inicial

O campo de pergunta continua fixo no rodapé, agora com a faixa de filtros logo acima dele, e é o mesmo nas duas situações, com a tela inicial ou com a conversa. A tela inicial fica mais curta, na ordem título, exemplos e nota explicativa. Os cartões de exemplo mantêm o formato atual. A nota explicativa fica com duas frases: a primeira diz que as respostas descrevem as avaliações recuperadas e não a base inteira, e a segunda diz que dá para continuar a conversa com perguntas curtas, como "E nas notas altas?". Depois da primeira pergunta, o conjunto de título, exemplos e nota continua sumindo, como hoje.

Como o campo fica no rodapé, os menus da faixa abrem para cima no computador, alinhados ao botão que os abriu, e nunca saem da tela. A página já mede a altura do campo fixo para reservar o espaço no fim da conversa, e essa medida passa a incluir a faixa.

## Acessibilidade e temas

Cada botão da faixa tem nome acessível completo, como "Filtrar por nota, nenhum selecionado", e o estado de aberto ou fechado é anunciado. As opções dos menus são navegáveis pelas setas e marcadas com os papéis corretos para leitor de tela. Quando um filtro é aplicado ou removido, um aviso curto anuncia a mudança, como "Filtro de nota aplicado: 1 e 2". As cores dos botões ativos têm contraste suficiente nos temas claro e escuro, e o botão ativo não depende só da cor: ele também mostra o valor e o x. As animações respeitam a preferência por movimento reduzido.

## A página como um todo

Revisei o resto da página no computador, no celular e nos dois temas, com a tela inicial, uma conversa em andamento e os estados de erro. O que segue é o que encontrei, com a sugestão para cada ponto.

### Chave de acesso

Ninguém consegue perguntar sem a chave, mas ela é um campo pequeno no canto do topo, fácil de não ver. Quem clica num exemplo sem a chave recebe só um aviso vermelho lá em cima. A chave errada só é descoberta depois da primeira pergunta, quando a resposta volta com erro. No celular, o campo ocupa uma linha inteira do topo durante toda a conversa.

A sugestão é tratar a chave como a porta de entrada. Sem chave guardada, a página abre com um cartão no centro, "Digite a chave de acesso para começar", com o campo, o botão "Entrar" e uma frase dizendo que a chave vem com o material de entrega do projeto. A chave é conferida na hora, com uma chamada à rota das categorias, que exige a chave e não consome a cota diária, e o erro aparece no próprio cartão. Com a chave aceita, o cartão some, o topo fica só com o nome, a situação da API, "Nova conversa" e o tema, e a chave vira um item discreto, "Trocar a chave". Essa mesma chamada já deixa as categorias carregadas para o filtro.

### API desligada

Fora do horário de funcionamento, a única indicação é o texto pequeno ao lado do ponto vermelho no topo. O campo de pergunta e os exemplos continuam ativos, e o gestor só descobre que o chat está desligado depois de perguntar.

A sugestão é uma faixa de aviso no alto do conteúdo, "O chat funciona das 9h às 22h, horário de Brasília. Volte nesse horário.", com o campo de pergunta e os exemplos desabilitados enquanto a API não responde. A página já volta a conferir a API de tempos em tempos, e a faixa some sozinha quando ela liga.

### O limite das respostas some depois da primeira pergunta

A nota que explica que as respostas descrevem as avaliações recuperadas, e não a base inteira, fica na tela inicial e desaparece com a primeira pergunta. É justamente durante a leitura das respostas que ela importa, e é o cuidado central do projeto.

A sugestão é uma linha curta no pé de cada resposta, "Baseada em 10 avaliações citadas, de 15 recuperadas para esta pergunta. Não mede a frequência na base inteira.", com os números daquela resposta. Ela substitui a nota fixa depois da primeira pergunta e ainda mostra, sem abrir nada, o tamanho da evidência.

### Ler a avaliação citada tira a resposta da tela

Clicar num número entre colchetes abre o bloco das avaliações e rola a página até o comentário. A frase que estava sendo lida sai da tela, e não há caminho de volta além de rolar para cima. Numa resposta com dez citações, conferir cada uma vira um vaivém.

A sugestão é mostrar o comentário num pequeno cartão ao lado da citação, aberto pelo clique, com a nota, a categoria, a entrega e o texto, e um link "Ver na lista" para quem quiser o bloco completo. No celular, o cartão abre como folha de baixo para cima, igual aos menus dos filtros. A resposta continua onde estava.

Em telas largas, a partir de 1.100 pixels, sobra muito espaço dos dois lados da coluna de 820 pixels. Uma segunda etapa pode usar esse espaço para um painel de evidências à direita, com as avaliações da resposta em foco, mas isso muda a estrutura da página e fica fora desta rodada.

### "Nova conversa" apaga tudo num clique

O botão fica ao lado do tema e da chave e apaga a conversa sem confirmação. Recarregar a página tem o mesmo efeito, porque a conversa vive só na memória.

A sugestão é, depois do clique, mostrar por alguns segundos um aviso com "Conversa apagada" e o botão "Desfazer", que é menos intrusivo do que uma pergunta de confirmação. Guardar a conversa no navegador para sobreviver ao recarregamento é possível, mas não é prioridade: a demonstração não depende disso.

### Textos pequenos e termos técnicos

O rodapé de cada avaliação usa letra de 12,5 pixels em cinza, abaixo do mínimo confortável de leitura. "Similaridade 0,71" é jargão, e a explicação está num `title`, que não aparece no toque nem para leitor de tela. O mesmo vale para o identificador completo da avaliação. As categorias aparecem sem acento, como "Moveis decoracao".

A sugestão é subir o rodapé para 13,5 pixels, trocar o rótulo para "Proximidade com a pergunta: 0,71" e levar a explicação e o identificador completo para o cartão da avaliação, visíveis ao tocar. Para as categorias, uma tabela com os nomes acentuados das cerca de setenta categorias da Olist, como "Móveis e decoração" e "Cama, mesa e banho", usada nos cartões e no filtro, com o nome original como reserva quando faltar na tabela.

### Usar a resposta fora da página

O gestor não tem como levar a resposta para um e-mail ou um relatório, a não ser selecionando o texto à mão, e os botões das citações atrapalham a seleção.

A sugestão é um botão "Copiar" em cada resposta, que copia o texto com os números das citações e, abaixo, a lista das avaliações citadas com o identificador de cada uma, para a evidência viajar junto.

### Contexto do projeto

A página não diz de onde vêm os dados nem de que período são. Quem avalia o projeto, ou um gestor curioso, não sabe que os comentários são de 2016 a 2018, de uma base pública, e que os nomes das lojas são fictícios.

A sugestão é um link "Sobre os dados" no topo, que abre um texto curto com a origem da base, o período, o número de comentários, o que o chat faz e o que ele não faz.

### Acessibilidade e teclado

Depois de enviar a pergunta, o foco fica no campo, o que está certo, mas não há atalho para pular do topo direto ao campo de pergunta, e as respostas não têm título para quem navega por títulos com leitor de tela. Numa conversa longa, não há como voltar ao fim depois de rolar para cima.

A sugestão é um link "Ir para a pergunta" visível só no foco do teclado, um título oculto em cada troca com o texto da pergunta e um botão flutuante "Ir para o fim" que aparece quando a última resposta está fora da tela.

### Ordem de execução

A entrega é em 17/11, e por isso separei em duas rodadas. A primeira, junto com os filtros, tem o que muda a primeira impressão e protege a leitura correta das respostas: a entrada pela chave, o aviso de API desligada, a linha de evidência no pé de cada resposta, o cartão da avaliação ao clicar na citação, o "Desfazer" da nova conversa e os textos pequenos e técnicos. A segunda, se sobrar tempo, tem os nomes acentuados das categorias, o botão de copiar, o "Sobre os dados" e os itens de teclado. O painel lateral de evidências e a conversa guardada no navegador ficam registrados como ideias, fora do prazo.

## Decisões tomadas

Três escolhas tinham alternativa e ficam registradas aqui. Os exemplos e as sugestões respeitam os filtros ativos, em vez de sempre buscarem em todas as avaliações, porque uma regra única é mais previsível do que uma exceção que o gestor teria de adivinhar. "Nova conversa" limpa os filtros, porque quem recomeça espera a página no estado inicial. Os filtros valem para a pergunta seguinte, em vez de voltarem a zero a cada envio, porque o uso mais comum é fazer várias perguntas sobre o mesmo recorte, como as notas baixas de uma categoria, e a linha de apoio mantém o critério à vista.

## O que não muda

A API, o formato do corpo enviado em `/api/ask`, a rota `/api/categories` e a lógica de `buildFilters` e `describeFilters` continuam como estão. Os textos vindos da API continuam entrando na tela com `textContent`, nunca como HTML, e o CI continua recusando `innerHTML` nos arquivos da página. A lista de sugestões e o botão de tema não são tocados.

## Como vou verificar

As funções novas que não dependem do navegador, como o texto da linha de apoio, o rótulo de cada botão, a filtragem da lista de categorias por texto, sem diferenciar acentos nem maiúsculas, os atalhos de notas baixas e altas e a frase do aviso quando o filtro restringe a busca, ficam em `frontend/logic.js` e ganham testes no Node. O resto é conferido no navegador, nos tamanhos de computador e de celular e nos dois temas, com um servidor local que imita a API, passando por estes casos: abrir cada menu e escolher um valor, remover um filtro pelo x, limpar tudo, enviar uma pergunta com filtros e conferir o balão, enviar a pergunta seguinte e conferir que os filtros foram mantidos, buscar uma categoria pelo nome, abrir o menu de categoria sem a chave e com a API fora do ar, receber uma resposta sem evidência com filtros e usar "Perguntar sem filtros", clicar num exemplo e numa sugestão com filtros ativos, usar "Tentar de novo" depois de mudar a faixa, começar uma nova conversa, usar só o teclado e conferir, na árvore de acessibilidade do navegador, os nomes e os estados dos botões e das opções.

## Pronto quando

Para os filtros: um gestor que abre a página pela primeira vez consegue, sem instrução, restringir a busca às avaliações de nota 1 em entregas com problema e ver, antes e depois de enviar, com que critério a busca está sendo feita. No celular, a faixa ocupa uma linha só, os menus abrem como folha e fecham sem deixar nada cobrindo a conversa, e todos os alvos de toque têm pelo menos 44 pixels. Um filtro que deixa a busca sem resultado é explicado na resposta, com o caminho para perguntar sem ele. Os testes do Node e o CI passam, e as decisões de design ficam registradas no fim da seção "Página do chat" do `docs/07`.

Para a primeira rodada da página: quem abre a página sem chave entende de imediato o que fazer e vê o erro de chave antes de perguntar; fora do horário, a página diz que o chat está desligado sem que seja preciso perguntar; cada resposta mostra em quantas avaliações se baseia; e dá para ler uma avaliação citada sem perder a frase que a citou.
