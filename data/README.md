# Dataset

El dataset (10 500 imágenes, 3 clases) **no se sube a GitHub por su tamaño (~580 MB)**.

Descárgalo de: https://huggingface.co/buckets/CJ305/proyecto-final-vision-artificial-epp-storage

Descarga con la CLI de Hugging Face (`pip install huggingface_hub`):

```bash
hf sync hf://buckets/CJ305/proyecto-final-vision-artificial-epp-storage ./data/safety-Helmet-Reflective-Jacket
``` y descomprímelo aquí, de modo que quede:

```
data/safety-Helmet-Reflective-Jacket/{train,valid,test}/{images,labels}
```
