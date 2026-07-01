# Gallery

## Four-panel scientific figure

![Cleanfig four-panel demo](demo.png)

```python
import cleanfig as cf

fig = cf.figure(width="double", height=8.0, grid=(2, 2), panel_labels=True)
# ...
fig.save("four_panels.svg")

