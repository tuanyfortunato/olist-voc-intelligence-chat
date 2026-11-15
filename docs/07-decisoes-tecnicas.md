# Decisões técnicas

Registro aqui as decisões tomadas em cada etapa do projeto, com o motivo de cada uma. O documento cresce junto com o código, e cada PR que envolve uma escolha acrescenta a sua parte.

## Dependências e qualidade do código

Separei as dependências em dois arquivos. O `requirements.txt` tem só o que a API e os scripts dos workflows usam, e é ele que vai para a imagem do contêiner. O `requirements-dev.txt` inclui o primeiro e acrescenta o que serve apenas ao desenvolvimento: o kernel do Jupyter para o notebook, o pytest e o Ruff. Com isso a imagem fica menor e não carrega ferramentas que nunca vai executar. Todas as versões estão fixadas, para que o CI, os workflows e a imagem usem exatamente os mesmos pacotes.

Para lint e formatação escolhi o Ruff, que faz os dois papéis em uma única ferramenta e roda em poucos segundos no CI. As regras ativadas cobrem erros comuns, ordem dos imports, sintaxe antiga do Python e alguns padrões que costumam esconder bugs. Deixei o notebook de exploração fora do Ruff, porque ele já foi revisado e reformatá-lo agora só mudaria a apresentação, sem ganho para a análise.

Os testes cobrem apenas o que não chama a AWS, e por isso o CI não precisa de nenhuma credencial. O primeiro teste confere que o download da base pula os arquivos que já estão na pasta, usando uma versão falsa da API do Kaggle, sem acesso à rede.
