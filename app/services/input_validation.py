import math

def validate_estimate_inputs(data):
    """Reject malformed geometry before creating project or estimate rows."""
    def check_numbers(value,path='input'):
        if isinstance(value,dict):
            for k,v in value.items(): check_numbers(v,path+'.'+k)
        elif isinstance(value,list):
            if len(value)>500: raise ValueError(path+': too many entries')
            for v in value: check_numbers(v,path)
        elif isinstance(value,(float,int)) and not isinstance(value,bool):
            if not math.isfinite(value) or value<0 or value>1e9: raise ValueError(path+': invalid numeric value')
    check_numbers(data)
    floors=data.get('floors_list') or data.get('floorsList') or []
    if not isinstance(floors,list) or len(floors)>10: raise ValueError('Use a list of up to 10 floors')
    if not floors:
        area=float(data.get('total_sqft') or data.get('totalSqft') or 0)
        floors=[{'floor_name':'Ground Floor','floor_area_sqft':area}]
    normalized=[]
    for floor in floors:
        if not isinstance(floor,dict): raise ValueError('Each floor must be an object')
        area=float(floor.get('floor_area_sqft') or floor.get('area') or float(floor.get('length') or 0)*float(floor.get('width') or 0))
        if not math.isfinite(area) or not 1<=area<=100000: raise ValueError('Each floor area must be between 1 and 100,000 sqft')
        normalized.append({**floor,'floor_area_sqft':area})
    floor_area=sum(f['floor_area_sqft'] for f in normalized)
    def dimension(key,alias=None):
        value=float(data.get(key) or (data.get(alias) if alias else 0) or 0)
        if not math.isfinite(value) or not 0<=value<=100000: raise ValueError('Invalid dimension: '+key)
        return value
    extra=dimension('portico_length')*dimension('portico_width')+dimension('staircase_length')*dimension('staircase_width')
    total=floor_area+extra
    if not 100<=total<=100000: raise ValueError('Total built-up area must be between 100 and 100,000 sqft')
    plot=dimension('plot_length','plotLength')*dimension('plot_width','plotWidth')
    if plot and normalized[0]['floor_area_sqft']+extra>plot: raise ValueError('Ground coverage exceeds the plot area')
    for key in ('contingency_percentage','builder_margin_percentage','gst_percentage'):
        if data.get(key) not in ('',None):
            val=float(data[key])
            if not math.isfinite(val) or not 0<=val<=100: raise ValueError(key+' must be between 0 and 100')
    rooms=data.get('rooms_list') or []
    if not isinstance(rooms,list) or any(not isinstance(r,dict) for r in rooms): raise ValueError('rooms_list must contain objects')
    for r in rooms:
        for key in ('length','width'):
            val=float(r.get(key) or 0)
            if not math.isfinite(val) or not 0<=val<=1000: raise ValueError('Invalid room '+key)
    data['floors_list']=normalized
    data['floors']=len(normalized)
    data['total_sqft']=total
    data['builtup_area_sqft']=total
    if data.get('quality','Standard') not in ('Base','Standard','Premium','Luxury'): raise ValueError('Unknown construction quality')
    return data
